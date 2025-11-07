"""
MAVLink Parser for PX4 Telemetry
Handles connection to PX4 SITL instances and parses key messages
Receives ALL messages for throughput calculation, but only parses 6 demo messages
"""

import time
import threading
from pymavlink import mavutil
from typing import Dict, Any, Optional
from collections import defaultdict
import logging

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
    """Manages connection to a single PX4 instance and parses telemetry"""

    def __init__(self, drone_id: int, name: str, host: str, port: int, color: str):
        self.drone_id = drone_id
        self.name = name
        self.host = host
        self.port = port
        self.color = color

        self.connection: Optional[mavutil.mavlink_connection] = None
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
        self.last_packet_time = None
        self.latencies = []

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
            # Use 'udp:' (client mode) not 'udpin:' (server mode)
            # PX4 broadcasts on these ports, we need to connect as a client
            connection_string = f"udpin:{self.host}:{self.port}"
            logger.info(f"{self.name}: Connecting to {connection_string}")

            self.connection = mavutil.mavlink_connection(
                connection_string,
                source_system=255,
                source_component=0
            )

            # Wait for heartbeat
            logger.info(f"{self.name}: Waiting for heartbeat...")
            self.connection.wait_heartbeat(timeout=10)

            self.telemetry["connected"] = True
            self.connection_start_time = time.time()  # Track when we connected
            logger.info(f"{self.name}: Connected successfully!")
            return True

        except Exception as e:
            logger.error(f"{self.name}: Connection failed: {e}")
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
        """Main listening loop for MAVLink messages"""
        while self.running:
            try:
                if not self.connection:
                    time.sleep(1)
                    continue

                msg = self.connection.recv_match(blocking=True, timeout=1.0)
                if msg is None:
                    continue

                # Update metrics for ALL messages
                current_time = time.time()
                msg_type = msg.get_type()

                # Track ALL messages for throughput
                self.total_packet_count += 1
                self.throughput_total_packets += 1
                self.message_type_counts[msg_type] += 1

                # Calculate inter-packet latency
                if self.last_packet_time:
                    latency_ms = (current_time - self.last_packet_time) * 1000
                    self.latencies.append(latency_ms)
                    if len(self.latencies) > 100:
                        self.latencies.pop(0)

                self.last_packet_time = current_time

                # Check if this is a demo message
                if msg_type in DEMO_MESSAGES:
                    # This is a message we care about
                    self.demo_packet_count += 1
                    self.throughput_demo_packets += 1
                    self.telemetry["last_update"] = current_time

                    # Parse the message
                    self._parse_message(msg)
                else:
                    # This is an extra PX4 message we're filtering out
                    self.filtered_packet_count += 1

            except Exception as e:
                logger.error(f"{self.name}: Error in listen loop: {e}")
                time.sleep(0.1)

    def _parse_message(self, msg):
        """Parse different MAVLink message types (only demo messages)"""
        msg_type = msg.get_type()

        if msg_type == "HEARTBEAT":
            self.telemetry["heartbeat"] = {
                "type": msg.type,
                "autopilot": msg.autopilot,
                "base_mode": msg.base_mode,
                "custom_mode": msg.custom_mode,
                "system_status": msg.system_status,
                "mavlink_version": msg.mavlink_version
            }

        elif msg_type == "GPS_RAW_INT":
            self.telemetry["gps"] = {
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
            self.telemetry["battery"] = {
                "id": msg.id,
                "voltage": msg.voltages[0] / 1000.0 if msg.voltages[0] != -1 else None,
                "current": msg.current_battery / 100.0 if msg.current_battery != -1 else None,
                "battery_remaining": msg.battery_remaining,
                "temperature": msg.temperature / 100.0 if msg.temperature != 32767 else None
            }

        elif msg_type == "ATTITUDE":
            self.telemetry["attitude"] = {
                "roll": msg.roll,
                "pitch": msg.pitch,
                "yaw": msg.yaw,
                "rollspeed": msg.rollspeed,
                "pitchspeed": msg.pitchspeed,
                "yawspeed": msg.yawspeed
            }

        elif msg_type == "GLOBAL_POSITION_INT":
            self.telemetry["position"] = {
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
            self.telemetry["vfr_hud"] = {
                "airspeed": msg.airspeed,
                "groundspeed": msg.groundspeed,
                "heading": msg.heading,
                "throttle": msg.throttle,
                "alt": msg.alt,
                "climb": msg.climb
            }

    def get_telemetry(self) -> Dict[str, Any]:
        """Get current telemetry snapshot"""
        return self.telemetry.copy()

    def get_metrics(self) -> Dict[str, Any]:
        """Calculate and return network metrics"""
        import statistics

        current_time = time.time()

        # Calculate sliding window rates (for real-time monitoring)
        window_duration = current_time - self.throughput_window_start
        if window_duration > 0:
            window_total_rate = self.throughput_total_packets / window_duration
            window_demo_rate = self.throughput_demo_packets / window_duration
        else:
            window_total_rate = 0
            window_demo_rate = 0

        # Reset window if it's been more than 1 second
        if window_duration >= 1.0:
            self.throughput_window_start = current_time
            self.throughput_total_packets = 0
            self.throughput_demo_packets = 0

        # Calculate overall average rates (for reporting)
        # This is more reliable than the sliding window for final stats
        if self.connection_start_time:
            overall_duration = current_time - self.connection_start_time
            if overall_duration > 0:
                overall_total_rate = self.total_packet_count / overall_duration
                overall_demo_rate = self.demo_packet_count / overall_duration
            else:
                overall_total_rate = 0
                overall_demo_rate = 0
        else:
            overall_total_rate = 0
            overall_demo_rate = 0

        # Use window rates if we're actively receiving (window has data)
        # Otherwise use overall rates (better for final stats)
        if window_duration < 1.0 and self.throughput_total_packets > 0:
            total_rate_hz = window_total_rate
            demo_rate_hz = window_demo_rate
        else:
            total_rate_hz = overall_total_rate
            demo_rate_hz = overall_demo_rate

        metrics = {
            # Packet counts
            "total_packet_count": self.total_packet_count,
            "demo_packet_count": self.demo_packet_count,
            "filtered_packet_count": self.filtered_packet_count,

            # Rates
            "total_rate_hz": round(total_rate_hz, 1),
            "demo_rate_hz": round(demo_rate_hz, 1),

            # Latency metrics
            "latency_ms": None,
            "jitter_ms": None,

            # Message type breakdown
            "message_types": dict(self.message_type_counts),
            "demo_message_types": len([t for t in self.message_type_counts.keys() if t in DEMO_MESSAGES]),
            "total_message_types": len(self.message_type_counts),
            "filtered_message_types": len([t for t in self.message_type_counts.keys() if t not in DEMO_MESSAGES])
        }

        if len(self.latencies) > 1:
            metrics["latency_ms"] = round(
                statistics.mean(self.latencies[-10:]), 2)
            metrics["jitter_ms"] = round(statistics.stdev(
                self.latencies[-10:]), 2) if len(self.latencies) > 2 else 0

        return metrics

    def get_detailed_stats(self) -> Dict[str, Any]:
        """Get detailed statistics including message type breakdown"""
        metrics = self.get_metrics()

        # Add detailed breakdown
        demo_msgs = {k: v for k, v in self.message_type_counts.items()
                     if k in DEMO_MESSAGES}
        filtered_msgs = {
            k: v for k, v in self.message_type_counts.items() if k not in DEMO_MESSAGES}

        return {
            **metrics,
            "demo_messages": demo_msgs,
            "filtered_messages": filtered_msgs,
            "filter_percentage": round(
                (self.filtered_packet_count / self.total_packet_count * 100)
                if self.total_packet_count > 0 else 0,
                1
            )
        }


class MAVLinkManager:
    """Manages multiple drone connections"""

    def __init__(self, drones_config: list):
        self.drones: Dict[int, DroneConnection] = {}

        for config in drones_config:
            drone = DroneConnection(
                drone_id=config["id"],
                name=config["name"],
                host=config["host"],
                port=config["port"],
                color=config["color"]
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
        """Get telemetry from all drones"""
        return {
            drone_id: drone.get_telemetry()
            for drone_id, drone in self.drones.items()
        }

    def get_all_metrics(self) -> Dict[int, Dict[str, Any]]:
        """Get network metrics from all drones"""
        return {
            drone_id: drone.get_metrics()
            for drone_id, drone in self.drones.items()
        }

    def get_all_detailed_stats(self) -> Dict[int, Dict[str, Any]]:
        """Get detailed statistics from all drones"""
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

            print(f"\n{drone.name} (ID: {drone_id})")
            print("-"*80)
            print(
                f"  Total Messages:    {stats['total_packet_count']:6d} @ {stats['total_rate_hz']:5.1f} Hz")
            print(
                f"  Demo Messages:     {stats['demo_packet_count']:6d} @ {stats['demo_rate_hz']:5.1f} Hz")
            print(
                f"  Filtered Messages: {stats['filtered_packet_count']:6d} ({stats['filter_percentage']:.1f}% filtered)")

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
