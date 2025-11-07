#!/usr/bin/env python3
"""
Telemetry Data Flow Debugger
Tests the complete data pipeline from MAVLink to Dashboard
"""

import sys
import time
import json
from pymavlink import mavutil
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_mavlink_raw(port, duration=10):
    """Test raw MAVLink reception from a single drone"""
    logger.info(f"{'='*70}")
    logger.info(f"Testing MAVLink on port {port}")
    logger.info(f"{'='*70}")

    try:
        # Connect using UDP client mode
        connection_string = f"udp:127.0.0.1:{port}"
        logger.info(f"Connecting to {connection_string}...")

        conn = mavutil.mavlink_connection(connection_string)

        logger.info("Waiting for heartbeat...")
        conn.wait_heartbeat(timeout=15)
        logger.info(f"✓ Connected to System ID: {conn.target_system}")

        # Track messages
        message_counts = {}
        demo_messages = {'HEARTBEAT', 'GPS_RAW_INT', 'GLOBAL_POSITION_INT',
                         'BATTERY_STATUS', 'ATTITUDE', 'VFR_HUD'}
        demo_data = {}

        logger.info(f"\nReceiving messages for {duration} seconds...\n")

        start_time = time.time()
        while time.time() - start_time < duration:
            msg = conn.recv_match(blocking=True, timeout=1.0)
            if msg is None:
                continue

            msg_type = msg.get_type()
            message_counts[msg_type] = message_counts.get(msg_type, 0) + 1

            # Capture demo messages
            if msg_type in demo_messages and msg_type not in demo_data:
                demo_data[msg_type] = msg
                logger.info(f"✓ Received {msg_type}")

        elapsed = time.time() - start_time
        total_messages = sum(message_counts.values())
        rate = total_messages / elapsed

        logger.info(f"\n{'='*70}")
        logger.info(f"RESULTS FOR PORT {port}")
        logger.info(f"{'='*70}")
        logger.info(f"Duration: {elapsed:.1f}s")
        logger.info(f"Total messages: {total_messages} ({rate:.1f} Hz)")
        logger.info(f"Unique message types: {len(message_counts)}")

        # Demo messages status
        logger.info(f"\nDemo Messages Status:")
        for msg_type in demo_messages:
            status = "✓ RECEIVED" if msg_type in demo_data else "✗ MISSING"
            count = message_counts.get(msg_type, 0)
            logger.info(f"  {msg_type:25s} {status:15s} ({count} msgs)")

        # Parse demo message content
        logger.info(f"\nDemo Message Content:")

        if 'HEARTBEAT' in demo_data:
            hb = demo_data['HEARTBEAT']
            logger.info(f"  HEARTBEAT:")
            logger.info(f"    System Status: {hb.system_status}")
            logger.info(f"    Autopilot: {hb.autopilot}")

        if 'GPS_RAW_INT' in demo_data:
            gps = demo_data['GPS_RAW_INT']
            logger.info(f"  GPS_RAW_INT:")
            logger.info(f"    Lat: {gps.lat / 1e7:.6f}°")
            logger.info(f"    Lon: {gps.lon / 1e7:.6f}°")
            logger.info(f"    Alt: {gps.alt / 1000.0:.1f}m")
            logger.info(f"    Satellites: {gps.satellites_visible}")
            logger.info(f"    Fix Type: {gps.fix_type}")

        if 'GLOBAL_POSITION_INT' in demo_data:
            pos = demo_data['GLOBAL_POSITION_INT']
            logger.info(f"  GLOBAL_POSITION_INT:")
            logger.info(f"    Lat: {pos.lat / 1e7:.6f}°")
            logger.info(f"    Lon: {pos.lon / 1e7:.6f}°")
            logger.info(f"    Alt: {pos.alt / 1000.0:.1f}m")
            logger.info(f"    Relative Alt: {pos.relative_alt / 1000.0:.1f}m")

        if 'BATTERY_STATUS' in demo_data:
            bat = demo_data['BATTERY_STATUS']
            logger.info(f"  BATTERY_STATUS:")
            logger.info(f"    Remaining: {bat.battery_remaining}%")
            logger.info(f"    Voltage: {bat.voltages[0] / 1000.0:.2f}V")

        if 'VFR_HUD' in demo_data:
            vfr = demo_data['VFR_HUD']
            logger.info(f"  VFR_HUD:")
            logger.info(f"    Groundspeed: {vfr.groundspeed:.1f} m/s")
            logger.info(f"    Heading: {vfr.heading}°")
            logger.info(f"    Altitude: {vfr.alt:.1f}m")

        # Top 10 message types
        logger.info(f"\nTop 10 Message Types:")
        sorted_msgs = sorted(message_counts.items(),
                             key=lambda x: x[1], reverse=True)
        for msg_type, count in sorted_msgs[:10]:
            rate = count / elapsed
            demo_marker = "📌" if msg_type in demo_messages else "  "
            logger.info(
                f"  {demo_marker} {msg_type:30s} {count:6d} msgs ({rate:6.1f} Hz)")

        conn.close()
        return True

    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)
        return False


def test_parser_output(port, duration=5):
    """Test the MAVLink parser output format"""
    logger.info(f"\n{'='*70}")
    logger.info(f"Testing Parser Output for Port {port}")
    logger.info(f"{'='*70}")

    # Import the parser
    try:
        from mavlink_parser import DroneConnection
    except ImportError:
        logger.error(
            "Cannot import mavlink_parser - make sure it's in the same directory")
        return False

    drone = DroneConnection(
        drone_id=1,
        name=f"Test Drone {port}",
        host="127.0.0.1",
        port=port,
        color="#FF0000"
    )

    logger.info("Connecting...")
    if not drone.connect():
        logger.error("Failed to connect")
        return False

    logger.info("Starting listener...")
    drone.start()

    logger.info(f"Collecting data for {duration} seconds...")
    time.sleep(duration)

    # Get telemetry
    telemetry = drone.get_telemetry()
    metrics = drone.get_metrics()

    logger.info(f"\nTelemetry Data:")
    logger.info(json.dumps(telemetry, indent=2, default=str))

    logger.info(f"\nMetrics Data:")
    logger.info(json.dumps(metrics, indent=2, default=str))

    # Validate critical fields
    logger.info(f"\nValidation:")
    logger.info(f"  Connected: {telemetry['connected']}")
    logger.info(
        f"  Has GPS: {'gps' in telemetry and telemetry['gps'] is not None}")
    logger.info(
        f"  Has Position: {'position' in telemetry and telemetry['position'] is not None}")
    logger.info(
        f"  Has Battery: {'battery' in telemetry and telemetry['battery'] is not None}")
    logger.info(
        f"  Has Heartbeat: {'heartbeat' in telemetry and telemetry['heartbeat'] is not None}")
    logger.info(f"  Demo packets: {metrics.get('demo_packet_count', 0)}")
    logger.info(f"  Total packets: {metrics.get('total_packet_count', 0)}")

    drone.stop()
    return True


def test_socketio_client(duration=10):
    """Test Socket.IO client connection and data reception"""
    logger.info(f"\n{'='*70}")
    logger.info(f"Testing Socket.IO Client")
    logger.info(f"{'='*70}")

    try:
        import socketio
    except ImportError:
        logger.error(
            "python-socketio not installed: pip install python-socketio")
        return False

    updates_received = []

    sio = socketio.Client()

    @sio.on('connect')
    def on_connect():
        logger.info("✓ Connected to Socket.IO server")
        sio.emit('start_streaming')

    @sio.on('connection_response')
    def on_connection_response(data):
        logger.info(f"✓ Connection response: {data}")

    @sio.on('streaming_status')
    def on_streaming_status(data):
        logger.info(f"✓ Streaming status: {data}")

    @sio.on('telemetry_update')
    def on_telemetry_update(data):
        updates_received.append(data)
        if len(updates_received) % 10 == 0:
            logger.info(f"Received {len(updates_received)} updates")

    @sio.on('disconnect')
    def on_disconnect():
        logger.info("Disconnected from server")

    try:
        logger.info("Connecting to http://localhost:5000...")
        sio.connect('http://localhost:5000')

        logger.info(f"Receiving updates for {duration} seconds...")
        time.sleep(duration)

        logger.info(f"\n{'='*70}")
        logger.info(f"Socket.IO Results")
        logger.info(f"{'='*70}")
        logger.info(f"Total updates received: {len(updates_received)}")

        if updates_received:
            latest = updates_received[-1]
            logger.info(f"Latest update timestamp: {latest.get('timestamp')}")
            logger.info(f"Number of drones: {len(latest.get('drones', []))}")

            for drone in latest.get('drones', []):
                logger.info(f"\n  Drone {drone['id']} ({drone['name']}):")
                logger.info(f"    Connected: {drone['connected']}")
                logger.info(f"    Position: {drone['position']}")
                logger.info(f"    Battery: {drone['battery_percent']}%")
                logger.info(f"    Packets: {drone['packet_count']}")
                logger.info(f"    Latency: {drone['latency_ms']}ms")

        sio.disconnect()
        return True

    except Exception as e:
        logger.error(f"❌ Socket.IO test failed: {e}", exc_info=True)
        return False


def main():
    """Run diagnostic tests"""
    print("\n" + "="*70)
    print("  PX4 Dashboard Telemetry Debugger")
    print("="*70)

    if len(sys.argv) < 2:
        print("\nUsage:")
        print("  python3 debug_telemetry.py raw <port>      # Test raw MAVLink")
        print("  python3 debug_telemetry.py parser <port>   # Test parser output")
        print("  python3 debug_telemetry.py socketio        # Test Socket.IO client")
        print("  python3 debug_telemetry.py all             # Run all tests")
        print("\nExamples:")
        print("  python3 debug_telemetry.py raw 14540")
        print("  python3 debug_telemetry.py all")
        sys.exit(1)

    test_type = sys.argv[1].lower()

    if test_type == 'raw':
        if len(sys.argv) < 3:
            print("Error: Port required for raw test")
            sys.exit(1)
        port = int(sys.argv[2])
        test_mavlink_raw(port)

    elif test_type == 'parser':
        if len(sys.argv) < 3:
            print("Error: Port required for parser test")
            sys.exit(1)
        port = int(sys.argv[2])
        test_parser_output(port)

    elif test_type == 'socketio':
        test_socketio_client()

    elif test_type == 'all':
        logger.info("Running comprehensive test suite...")

        # Test all three ports
        ports = [14540, 14541, 14542]
        for port in ports:
            logger.info(f"\n{'#'*70}")
            logger.info(f"Testing Port {port}")
            logger.info(f"{'#'*70}")
            test_mavlink_raw(port, duration=5)
            time.sleep(2)

        # Test Socket.IO
        logger.info(f"\n{'#'*70}")
        logger.info(f"Testing Socket.IO Client")
        logger.info(f"{'#'*70}")
        test_socketio_client(duration=10)

    else:
        print(f"Unknown test type: {test_type}")
        sys.exit(1)


if __name__ == "__main__":
    main()
