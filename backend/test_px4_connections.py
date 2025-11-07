#!/usr/bin/env python3
"""
Quick Connection Test for PX4 Multi-Vehicle Setup
Tests each drone port individually
"""

from pymavlink import mavutil
import sys
import time


def test_connection(port, timeout=15):
    """Test connection to a single PX4 instance"""
    connection_string = f"udp:127.0.0.1:{port}"

    print(f"\n{'='*60}")
    print(f"Testing: {connection_string}")
    print('='*60)

    try:
        print(f"[1/3] Creating connection...")
        conn = mavutil.mavlink_connection(
            connection_string,
            source_system=255,
            source_component=0
        )

        print(f"[2/3] Waiting for heartbeat (timeout: {timeout}s)...")
        start_time = time.time()
        conn.wait_heartbeat(timeout=timeout)
        elapsed = time.time() - start_time

        print(f"✓ Heartbeat received in {elapsed:.2f}s")
        print(f"  System ID: {conn.target_system}")
        print(f"  Component ID: {conn.target_component}")

        print(f"\n[3/3] Receiving messages (5 seconds)...")
        msg_types = set()
        msg_count = 0
        end_time = time.time() + 5

        while time.time() < end_time:
            msg = conn.recv_match(blocking=True, timeout=1.0)
            if msg:
                msg_count += 1
                msg_types.add(msg.get_type())

        print(f"✓ Received {msg_count} messages")
        print(f"  Message types: {', '.join(sorted(msg_types))}")

        # Check for key messages
        required_msgs = {'HEARTBEAT', 'GPS_RAW_INT', 'GLOBAL_POSITION_INT'}
        found = required_msgs.intersection(msg_types)
        missing = required_msgs - msg_types

        if found:
            print(f"✓ Found demo messages: {', '.join(found)}")
        if missing:
            print(f"⚠ Missing demo messages: {', '.join(missing)}")

        conn.close()
        return True

    except Exception as e:
        print(f"✗ Connection FAILED: {e}")
        return False


def main():
    """Test all three drone ports"""
    ports = [14540, 14541, 14542]
    drone_names = ["Drone Alpha", "Drone Bravo", "Drone Charlie"]

    print("\n" + "="*60)
    print("  PX4 Multi-Vehicle Connection Test")
    print("="*60)
    print("\nThis script tests UDP client connections to three PX4 SITL instances")
    print("Make sure PX4 instances are running first!")
    print("\nUsage:")
    print("  ./test_connections.py              # Test all three drones")
    print("  ./test_connections.py 14541        # Test specific port")
    print()

    # Check if specific port provided
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
            ports = [port]
            drone_names = [f"Drone on port {port}"]
        except ValueError:
            print(f"Error: Invalid port '{sys.argv[1]}'")
            sys.exit(1)

    results = {}

    for port, name in zip(ports, drone_names):
        print(f"\n{'='*60}")
        print(f"  {name} - Port {port}")
        print('='*60)
        results[port] = test_connection(port)
        time.sleep(1)  # Brief pause between tests

    # Summary
    print("\n" + "="*60)
    print("  SUMMARY")
    print("="*60)

    success_count = sum(results.values())
    total_count = len(results)

    for port, name in zip(ports, drone_names):
        status = "✓ CONNECTED" if results[port] else "✗ FAILED"
        print(f"  Port {port} ({name}): {status}")

    print(f"\n  Total: {success_count}/{total_count} connections successful")

    if success_count < total_count:
        print("\n⚠ Some connections failed!")
        print("\nTroubleshooting:")
        print("  1. Check PX4 is running: ps aux | grep px4")
        print("  2. Check PX4 logs: tail -f /tmp/px4_logs/px4_*.log")
        print("  3. Verify MAVLink ports: grep -i mavlink /tmp/px4_logs/*.log")
        print("  4. Test UDP ports: nc -u -z -v 127.0.0.1 14540-14542")
        sys.exit(1)
    else:
        print("\n✓ All connections successful!")
        print("  Your PX4 setup is working correctly.")
        print("  You can now start the dashboard backend.")
        sys.exit(0)


if __name__ == "__main__":
    main()
