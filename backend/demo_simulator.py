"""
Demo Data Simulator
Simulates MAVLink telemetry for testing without PX4 instances
Usage: python demo_simulator.py
"""

import socket
import time
import random
import math
from pymavlink import mavutil


def create_mavlink_connection(port):
    """Create MAVLink UDP connection"""
    return mavutil.mavlink_connection(f'udpout:localhost:{port}', source_system=1)


def simulate_drone(drone_id, port, base_lat=37.7749, base_lon=-122.4194):
    """Simulate a single drone's telemetry"""
    print(f"Starting simulator for Drone {drone_id} on port {port}")

    # Create MAVLink connection
    mav = create_mavlink_connection(port)

    # Initial position
    lat = base_lat + (drone_id * 0.001)  # Offset drones slightly
    lon = base_lon + (drone_id * 0.001)
    alt = 0

    # Movement parameters
    heading = random.uniform(0, 360)
    speed = 5.0  # m/s

    start_time = time.time()
    sequence = 0

    while True:
        try:
            current_time = time.time()
            elapsed = current_time - start_time

            # Simulate circular flight path
            radius = 0.0002  # degrees (roughly 20m)
            angular_speed = 0.1  # radians per second
            angle = elapsed * angular_speed

            lat = base_lat + (drone_id * 0.001) + radius * math.cos(angle)
            lon = base_lon + (drone_id * 0.001) + radius * math.sin(angle)
            alt = 50 + 10 * math.sin(elapsed * 0.2)  # Oscillating altitude
            heading = (angle * 180 / math.pi) % 360

            # Send HEARTBEAT
            mav.mav.heartbeat_send(
                mavutil.mavlink.MAV_TYPE_QUADROTOR,
                mavutil.mavlink.MAV_AUTOPILOT_PX4,
                0,  # base_mode
                0,  # custom_mode
                mavutil.mavlink.MAV_STATE_ACTIVE,
                3   # mavlink_version
            )

            # Send GPS_RAW_INT
            mav.mav.gps_raw_int_send(
                int(elapsed * 1e6),  # time_usec in microseconds since start
                3,  # fix_type (3D fix)
                int(lat * 1e7),
                int(lon * 1e7),
                int(alt * 1000),
                100,  # eph (HDOP * 100)
                100,  # epv (VDOP * 100)
                int(speed * 100),  # vel (cm/s)
                int(heading * 100),  # cog
                10 + drone_id  # satellites_visible
            )

            # Send GLOBAL_POSITION_INT
            mav.mav.global_position_int_send(
                int(elapsed * 1e6),
                int(lat * 1e7),
                int(lon * 1e7),
                int(alt * 1000),
                int(alt * 1000),  # relative_alt
                int(speed * math.cos(angle * math.pi / 180) * 100),  # vx
                int(speed * math.sin(angle * math.pi / 180) * 100),  # vy
                0,  # vz
                int(heading * 100)
            )

            # Send BATTERY_STATUS
            battery_percent = 100 - (elapsed % 100)  # Slowly drain
            # First cell at 14.8V, rest unused (UINT16_MAX)
            voltages = [int(14.8 * 100)] + [65535] * 9
            mav.mav.battery_status_send(
                0,  # id
                0,  # battery_function
                0,  # type
                32767,  # temperature (invalid)
                voltages,  # voltages array [10] in millivolts
                int(10.5 * 100),  # current_battery
                -1,  # current_consumed
                -1,  # energy_consumed
                int(battery_percent),  # battery_remaining
            )

            # Send ATTITUDE
            mav.mav.attitude_send(
                int(elapsed * 1e6),
                math.sin(elapsed * 0.5) * 0.1,  # roll
                math.cos(elapsed * 0.5) * 0.1,  # pitch
                heading * math.pi / 180,  # yaw
                0.01,  # rollspeed
                0.01,  # pitchspeed
                0.02   # yawspeed
            )

            # Send VFR_HUD
            mav.mav.vfr_hud_send(
                speed,  # airspeed
                speed,  # groundspeed
                int(heading),
                50,  # throttle
                alt,
                0.5  # climb
            )

            sequence += 1
            time.sleep(0.05)  # 20 Hz update rate

        except KeyboardInterrupt:
            print(f"\nStopping simulator for Drone {drone_id}")
            break
        except Exception as e:
            print(f"Error in drone {drone_id} simulator: {e}")
            time.sleep(1)


if __name__ == "__main__":
    import threading

    print("=" * 60)
    print("  PX4 Telemetry Simulator")
    print("=" * 60)
    print("")
    print("Simulating 3 drones:")
    print("  - Drone 1: localhost:14540")
    print("  - Drone 2: localhost:14541")
    print("  - Drone 3: localhost:14542")
    print("")
    print("Press Ctrl+C to stop")
    print("=" * 60)
    print("")

    # Start simulators in separate threads
    threads = []
    for i in range(3):
        drone_id = i + 1
        port = 14540 + i
        thread = threading.Thread(
            target=simulate_drone,
            args=(drone_id, port),
            daemon=True
        )
        thread.start()
        threads.append(thread)

    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\nShutting down simulators...")
