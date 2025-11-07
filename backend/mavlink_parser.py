"""
MAVLink Parser for PX4 Telemetry - FIXED VERSION
Key fixes:
1. Changed UDP client mode to UDP server mode (udpin:)
2. Added system ID filtering to prevent message cross-contamination
3. Fixed lock ordering to prevent deadlocks
4. Fixed counter reset race condition
"""

import time
import threading
from pymavlink import mavutil
from typing import Dict, Any, Optional
from collections import defaultdict, deque
import logging
from copy import deepcopy

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define the 6 message types from demo_simulator.py
DEMO_MESSAGES = {
    'HEARTBEAT',
    'GPS_RAW_INT',
    'GLOBAL_POSITION_INT',
    'BATTERY_STATUS',
    'ATTITUDE',
    'VFR_HUD'
}


class DroneConnection:
    """Manages connection to a single PX4 instance and parses telemetry - THREAD-SAFE + FIXED"""

    def __init__(self, drone_id: int, name: str, host: str, port: int, color: str, expected_system_id: int):
        self.drone_id = drone_id
        self.name = name
        self.host = host
        self.port = port
        self.color = color
        self.expected_system_id = expected_system_id  # FIX: Track expected system ID

        self.connection: Optional[mavutil.mavlink_connection] = None

        # Thread safety locks
        self._telemetry_lock = threading.Lock()
        self._metrics_lock = threading.Lock()
        self._counts_lock = threading.Lock()

        self.telemetry: Dict[str, Any] = {
            "id": drone_id,
            "name": name,
            "color": color,
            "connected": False,
            "heartbeat": None,
            "gps": None,
            "battery": None,
            "attitude": None,
            "position": None,
            "vfr_hud": None,
            "last_update": None
        }

        self.running = False
        self.thread: Optional[threading.Thread] = None

        # Network metrics - track ALL messages
        self.total_packet_count = 0  # All messages received
        self.demo_packet_count = 0   # Only demo messages
        self.filtered_packet_count = 0  # Messages filtered out
        self.wrong_system_count = 0  # FIX: Track messages from wrong system
        self.last_packet_time = None

        # Use deque with maxlen for bounded buffer (thread-safer)
        self.latencies = deque(maxlen=100)

        # Message type tracking
        self.message_type_counts = defaultdict(int)

        # Throughput calculation (sliding window)
        self.throughput_window_start = time.time()
        self.throughput_total_packets = 0
        self.throughput_demo_packets = 0

        # Overall statistics (for final reporting)
        self.connection_start_time = None

    def connect(self):
        """Establish connection to PX4 instance"""
        try:
            # Close any existing connection first
            if self.connection:
                try:
                    self.connection.close()
                except:
                    pass
                self.connection = None
                time.sleep(0.5)  # Brief pause to ensure socket cleanup

            # FIX: Use 'udpin:' (server mode) instead of 'udp:' (client mode)
            # This creates a dedicated UDP server listening on the specific port
            # Prevents port competition between multiple drone connections
            connection_string = f"udpin:{self.host}:{self.port}"
            logger.info(
                f"{self.name}: Connecting to {connection_string} (expecting system ID {self.expected_system_id})")

            self.connection = mavutil.mavlink_connection(
                connection_string,
                source_system=255,
                source_component=0,
                retries=3,
                timeout=10
            )

            # Wait for heartbeat with longer timeout
            logger.info(
                f"{self.name}: Waiting for heartbeat from system {self.expected_system_id}...")

            # FIX: Wait for heartbeat from the CORRECT system
            start_time = time.time()
            while time.time() - start_time < 15:
                heartbeat = self.connection.recv_match(
                    type='HEARTBEAT', blocking=True, timeout=1)
                if heartbeat and heartbeat.get_srcSystem() == self.expected_system_id:
                    logger.info(
                        f"{self.name}: Got heartbeat from system {self.expected_system_id}")
                    break
                elif heartbeat:
                    logger.debug(
                        f"{self.name}: Ignoring heartbeat from system {heartbeat.get_srcSystem()}")
            else:
                logger.error(
                    f"{self.name}: No heartbeat received from system {self.expected_system_id}")
                return False

            # Thread-safe update
            with self._telemetry_lock:
                self.telemetry["connected"] = True

            with self._metrics_lock:
                self.connection_start_time = time.time()  # Track when we connected

            logger.info(
                f"{self.name}: Connected successfully to system {self.expected_system_id}!")
            return True

        except Exception as e:
            logger.error(f"{self.name}: Connection failed: {e}")
            with self._telemetry_lock:
                self.telemetry["connected"] = False
            return False

    def start(self):
        """Start listening thread"""
        if self.running:
            return

        self.running = True
        self.thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.thread.start()
        logger.info(f"{self.name}: Listening thread started")

    def stop(self):
        """Stop listening thread"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        logger.info(f"{self.name}: Stopped")

    def _listen_loop(self):
        """Main listening loop for MAVLink messages with connection health monitoring"""
        consecutive_timeouts = 0
        max_consecutive_timeouts = 15  # 15 * 2s = 30 seconds before reconnection
        reconnect_attempts = 0
        max_reconnect_attempts = 3

        while self.running:
            try:
                if not self.connection:
                    time.sleep(1)
                    continue

                msg = self.connection.recv_match(blocking=True, timeout=2.0)
                if msg is None:
                    # Check for connection health
                    consecutive_timeouts += 1
                    if consecutive_timeouts >= max_consecutive_timeouts:
                        logger.warning(
                            f"{self.name}: No messages for {max_consecutive_timeouts * 2} seconds, "
                            "attempting reconnection..."
                        )
                        with self._telemetry_lock:
                            self.telemetry["connected"] = False

                        # Attempt reconnection
                        if reconnect_attempts < max_reconnect_attempts:
                            reconnect_attempts += 1
                            logger.info(
                                f"{self.name}: Reconnection attempt {reconnect_attempts}/{max_reconnect_attempts}")

                            # Close old connection
                            try:
                                if self.connection:
                                    self.connection.close()
                            except:
                                pass

                            # Wait a bit before reconnecting
                            time.sleep(2)

                            # Try to reconnect
                            if self.connect():
                                logger.info(
                                    f"{self.name}: Reconnection successful!")
                                consecutive_timeouts = 0
                                reconnect_attempts = 0
                            else:
                                logger.error(
                                    f"{self.name}: Reconnection failed")
                        else:
                            logger.error(
                                f"{self.name}: Max reconnection attempts reached")
                            reconnect_attempts = 0  # Reset for future attempts
                            time.sleep(10)  # Wait longer before trying again

                        consecutive_timeouts = 0
                    continue

                # FIX: Filter by system ID FIRST before any processing
                msg_system_id = msg.get_srcSystem()
                if msg_system_id != self.expected_system_id:
                    # System ID 0 is GCS/Simulator - this is NORMAL, not an error
                    # Only count as "wrong" if it's from ANOTHER DRONE (not 0, not ours)
                    if msg_system_id != 0:
                        with self._counts_lock:
                            self.wrong_system_count += 1
                        # Don't log every message to avoid spam, but log periodically
                        if self.wrong_system_count % 100 == 1:
                            logger.debug(f"{self.name}: Ignoring message from OTHER DRONE system {msg_system_id} "
                                         f"(expected {self.expected_system_id})")
                    # Skip processing for ANY non-matching system ID (including 0)
                    # We only want to process messages from OUR drone
                    continue

                # Reset timeout counter on successful message FROM CORRECT SYSTEM
                consecutive_timeouts = 0
                reconnect_attempts = 0  # Reset on successful message

                # Ensure connected status is set
                with self._telemetry_lock:
                    if not self.telemetry["connected"]:
                        self.telemetry["connected"] = True
                        logger.info(f"{self.name}: Connection restored")

                # Update metrics for ALL messages from OUR system
                current_time = time.time()
                msg_type = msg.get_type()

                # Atomic counter updates with lock
                with self._counts_lock:
                    self.total_packet_count += 1
                    self.throughput_total_packets += 1
                    self.message_type_counts[msg_type] += 1

                # Thread-safe latency calculation
                with self._metrics_lock:
                    # Calculate inter-packet latency
                    if self.last_packet_time:
                        latency_ms = (
                            current_time - self.last_packet_time) * 1000
                        # deque with maxlen handles bounds automatically
                        self.latencies.append(latency_ms)

                    self.last_packet_time = current_time

                # Check if this is a demo message
                if msg_type in DEMO_MESSAGES:
                    # This is a message we care about
                    with self._counts_lock:
                        self.demo_packet_count += 1
                        self.throughput_demo_packets += 1

                    # Update last_update with lock
                    with self._telemetry_lock:
                        self.telemetry["last_update"] = current_time

                    # Parse the message (this updates telemetry with lock inside)
                    self._parse_message(msg)
                else:
                    # This is an extra PX4 message we're filtering out
                    with self._counts_lock:
                        self.filtered_packet_count += 1

            except Exception as e:
                logger.error(f"{self.name}: Error in listen loop: {e}")
                time.sleep(0.1)

    def _parse_message(self, msg):
        """Parse different MAVLink message types (only demo messages)"""
        msg_type = msg.get_type()

        # Build update dict first, then apply atomically
        update = {}

        if msg_type == "HEARTBEAT":
            update["heartbeat"] = {
                "type": msg.type,
                "autopilot": msg.autopilot,
                "base_mode": msg.base_mode,
                "custom_mode": msg.custom_mode,
                "system_status": msg.system_status,
                "mavlink_version": msg.mavlink_version
            }

        elif msg_type == "GPS_RAW_INT":
            update["gps"] = {
                "lat": msg.lat / 1e7,  # Convert to degrees
                "lon": msg.lon / 1e7,
                "alt": msg.alt / 1000.0,  # Convert to meters
                "eph": msg.eph / 100.0,  # GPS HDOP
                "epv": msg.epv / 100.0,  # GPS VDOP
                "vel": msg.vel / 100.0,  # Ground speed m/s
                "cog": msg.cog / 100.0,  # Course over ground
                "fix_type": msg.fix_type,
                "satellites_visible": msg.satellites_visible
            }

        elif msg_type == "BATTERY_STATUS":
            update["battery"] = {
                "id": msg.id,
                "voltage": msg.voltages[0] / 1000.0 if msg.voltages[0] != -1 else None,
                "current": msg.current_battery / 100.0 if msg.current_battery != -1 else None,
                "battery_remaining": msg.battery_remaining,
                "temperature": msg.temperature / 100.0 if msg.temperature != 32767 else None
            }

        elif msg_type == "ATTITUDE":
            update["attitude"] = {
                "roll": msg.roll,
                "pitch": msg.pitch,
                "yaw": msg.yaw,
                "rollspeed": msg.rollspeed,
                "pitchspeed": msg.pitchspeed,
                "yawspeed": msg.yawspeed
            }

        elif msg_type == "GLOBAL_POSITION_INT":
            update["position"] = {
                "lat": msg.lat / 1e7,
                "lon": msg.lon / 1e7,
                "alt": msg.alt / 1000.0,
                "relative_alt": msg.relative_alt / 1000.0,
                "vx": msg.vx / 100.0,  # m/s
                "vy": msg.vy / 100.0,
                "vz": msg.vz / 100.0,
                "hdg": msg.hdg / 100.0  # degrees
            }

        elif msg_type == "VFR_HUD":
            update["vfr_hud"] = {
                "airspeed": msg.airspeed,
                "groundspeed": msg.groundspeed,
                "heading": msg.heading,
                "throttle": msg.throttle,
                "alt": msg.alt,
                "climb": msg.climb
            }

        # Apply all updates atomically
        if update:
            with self._telemetry_lock:
                self.telemetry.update(update)

    def get_telemetry(self) -> Dict[str, Any]:
        """Get current telemetry snapshot - THREAD-SAFE"""
        # Deep copy with lock to prevent race conditions
        with self._telemetry_lock:
            return deepcopy(self.telemetry)

    def get_metrics(self) -> Dict[str, Any]:
        """Calculate and return network metrics - THREAD-SAFE with FIXED lock ordering"""
        import statistics

        current_time = time.time()

        # FIX: Acquire ALL locks once at the start in consistent order
        # Always: _metrics_lock THEN _counts_lock (nested)
        with self._metrics_lock:
            with self._counts_lock:
                # Snapshot ALL data at once while holding both locks
                total_packets = self.total_packet_count
                demo_packets = self.demo_packet_count
                filtered_packets = self.filtered_packet_count
                wrong_system = self.wrong_system_count
                throughput_total = self.throughput_total_packets
                throughput_demo = self.throughput_demo_packets
                window_start = self.throughput_window_start
                conn_start = self.connection_start_time
                latencies_copy = list(self.latencies)
                message_types = dict(self.message_type_counts)

                # Calculate window duration
                window_duration = current_time - window_start

                # FIX: Reset window while still holding both locks (prevents TOCTOU)
                if window_duration >= 1.0:
                    self.throughput_window_start = current_time
                    self.throughput_total_packets = 0
                    self.throughput_demo_packets = 0

        # All locks released - now do calculations without locks
        if window_duration > 0:
            window_total_rate = throughput_total / window_duration
            window_demo_rate = throughput_demo / window_duration
        else:
            window_total_rate = 0
            window_demo_rate = 0

        # Calculate overall average rates (for reporting)
        if conn_start:
            overall_duration = current_time - conn_start
            if overall_duration > 0:
                overall_total_rate = total_packets / overall_duration
                overall_demo_rate = demo_packets / overall_duration
            else:
                overall_total_rate = 0
                overall_demo_rate = 0
        else:
            overall_total_rate = 0
            overall_demo_rate = 0

        # Use window rates if we're actively receiving (window has data)
        # Otherwise use overall rates (better for final stats)
        if window_duration < 1.0 and throughput_total > 0:
            total_rate_hz = window_total_rate
            demo_rate_hz = window_demo_rate
        else:
            total_rate_hz = overall_total_rate
            demo_rate_hz = overall_demo_rate

        metrics = {
            # Packet counts
            "total_packet_count": total_packets,
            "demo_packet_count": demo_packets,
            "filtered_packet_count": filtered_packets,
            "wrong_system_count": wrong_system,  # FIX: Add this metric

            # Rates
            "total_rate_hz": round(total_rate_hz, 1),
            "demo_rate_hz": round(demo_rate_hz, 1),

            # Latency metrics
            "latency_ms": None,
            "jitter_ms": None,

            # Message type breakdown
            "message_types": message_types,
            "demo_message_types": len([t for t in message_types.keys() if t in DEMO_MESSAGES]),
            "total_message_types": len(message_types),
            "filtered_message_types": len([t for t in message_types.keys() if t not in DEMO_MESSAGES])
        }

        # Calculate latency stats from copied data
        if len(latencies_copy) > 1:
            recent_latencies = latencies_copy[-10:] if len(
                latencies_copy) >= 10 else latencies_copy
            metrics["latency_ms"] = round(statistics.mean(recent_latencies), 2)
            metrics["jitter_ms"] = round(
                statistics.stdev(recent_latencies), 2
            ) if len(recent_latencies) > 2 else 0

        return metrics

    def get_detailed_stats(self) -> Dict[str, Any]:
        """Get detailed statistics including message type breakdown - THREAD-SAFE"""
        metrics = self.get_metrics()

        # Add detailed breakdown (using already-copied message_types from metrics)
        message_types = metrics["message_types"]
        demo_msgs = {k: v for k, v in message_types.items()
                     if k in DEMO_MESSAGES}
        filtered_msgs = {
            k: v for k, v in message_types.items() if k not in DEMO_MESSAGES}

        return {
            **metrics,
            "demo_messages": demo_msgs,
            "filtered_messages": filtered_msgs,
            "filter_percentage": round(
                (metrics["filtered_packet_count"] /
                 metrics["total_packet_count"] * 100)
                if metrics["total_packet_count"] > 0 else 0,
                1
            )
        }


class MAVLinkManager:
    """Manages multiple drone connections - THREAD-SAFE"""

    def __init__(self, drones_config: list):
        self.drones: Dict[int, DroneConnection] = {}

        for config in drones_config:
            drone = DroneConnection(
                drone_id=config["id"],
                name=config["name"],
                host=config["host"],
                port=config["port"],
                color=config["color"],
                # FIX: Use system_id from config
                expected_system_id=config.get("system_id", config["id"])
            )
            self.drones[config["id"]] = drone

    def connect_all(self):
        """Connect to all drones"""
        for drone in self.drones.values():
            if drone.connect():
                drone.start()

    def stop_all(self):
        """Stop all drone connections"""
        for drone in self.drones.values():
            drone.stop()

    def get_all_telemetry(self) -> Dict[int, Dict[str, Any]]:
        """Get telemetry from all drones - THREAD-SAFE"""
        return {
            drone_id: drone.get_telemetry()
            for drone_id, drone in self.drones.items()
        }

    def get_all_metrics(self) -> Dict[int, Dict[str, Any]]:
        """Get network metrics from all drones - THREAD-SAFE"""
        return {
            drone_id: drone.get_metrics()
            for drone_id, drone in self.drones.items()
        }

    def get_all_detailed_stats(self) -> Dict[int, Dict[str, Any]]:
        """Get detailed statistics from all drones - THREAD-SAFE"""
        return {
            drone_id: drone.get_detailed_stats()
            for drone_id, drone in self.drones.items()
        }

    def print_stats(self):
        """Print comprehensive statistics"""
        print("\n" + "="*80)
        print("  MAVLink Message Statistics")
        print("="*80)

        for drone_id, drone in self.drones.items():
            stats = drone.get_detailed_stats()

            print(
                f"\n{drone.name} (ID: {drone_id}, System ID: {drone.expected_system_id})")
            print("-"*80)
            print(
                f"  Total Messages:    {stats['total_packet_count']:6d} @ {stats['total_rate_hz']:5.1f} Hz")
            print(
                f"  Demo Messages:     {stats['demo_packet_count']:6d} @ {stats['demo_rate_hz']:5.1f} Hz")
            print(
                f"  Filtered Messages: {stats['filtered_packet_count']:6d} ({stats['filter_percentage']:.1f}% filtered)")
            print(
                f"  Wrong System:      {stats['wrong_system_count']:6d} (from other drones)")

            print(f"\n  Demo Message Types ({stats['demo_message_types']}):")
            for msg_type, count in sorted(stats['demo_messages'].items()):
                print(f"    {msg_type:30s} {count:6d}")

            print(
                f"\n  Filtered Message Types ({stats['filtered_message_types']}):")
            filtered_list = list(stats['filtered_messages'].items())
            for msg_type, count in sorted(filtered_list, key=lambda x: x[1], reverse=True)[:10]:
                print(f"    {msg_type:30s} {count:6d}")
            if len(filtered_list) > 10:
                print(f"    ... and {len(filtered_list) - 10} more types")

        print("="*80 + "\n")
