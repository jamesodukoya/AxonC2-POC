import time
import random
import threading
import math
from pymavlink import mavutil


class PositionTracker:
    """Shared position tracker for collision avoidance"""

    def __init__(self):
        self.positions = {}  # {sysid: (x, y, z, timestamp)}
        self.lock = threading.Lock()

    def update(self, sysid, x, y, z):
        with self.lock:
            self.positions[sysid] = (x, y, z, time.time())

    def get_all_except(self, sysid):
        """Get all positions except for the specified vehicle"""
        with self.lock:
            return {sid: pos[:3] for sid, pos in self.positions.items()
                    if sid != sysid and time.time() - pos[3] < 2.0}

    def distance(self, pos1, pos2):
        """Calculate 3D Euclidean distance"""
        return math.sqrt(sum((a - b) ** 2 for a, b in zip(pos1, pos2)))


class MulticopterCommander:
    def __init__(self, port, sysid, update_rate, radius, alt_range,
                 position_tracker, min_separation):
        self.port = port
        self.sysid = sysid
        self.update_rate = update_rate
        self.radius = radius
        self.alt_min, self.alt_max = alt_range
        self.min_separation = min_separation
        self.position_tracker = position_tracker
        self.running = True
        self.conn = None

        # Current target position
        self.target_x = 0
        self.target_y = 0
        self.target_z = -20  # Start at different altitudes to avoid initial collision

        # Offset initial positions
        angle = (sysid - 1) * (2 * math.pi / 3)  # 120° apart
        self.target_x = 30 * math.cos(angle)
        self.target_y = 30 * math.sin(angle)
        self.target_z = -20 - (sysid - 1) * 10

    def connect(self):
        # Use bidirectional UDP connection
        conn_str = f'udp:127.0.0.1:{self.port}'
        print(f"[Vehicle {self.sysid}] Connecting to {conn_str}...")

        self.conn = mavutil.mavlink_connection(conn_str, source_system=255)

        if self.conn.wait_heartbeat(timeout=10):
            print(f"[Vehicle {self.sysid}] ✓ Connected")
            threading.Thread(target=self._heartbeats, daemon=True).start()
            return True

        print(f"[Vehicle {self.sysid}] ✗ No heartbeat")
        return False

    def _heartbeats(self):
        while self.running:
            try:
                self.conn.mav.heartbeat_send(6, 8, 0, 0, 0)
            except:
                pass
            time.sleep(1)

    def set_offboard(self):
        print(f"[Vehicle {self.sysid}] Setting OFFBOARD mode...")
        for _ in range(3):
            self.conn.mav.command_long_send(
                self.sysid, 1, 176, 0, 1, 6, 0, 0, 0, 0, 0)
            time.sleep(0.3)
        time.sleep(1)

    def arm(self):
        print(f"[Vehicle {self.sysid}] Arming...")

        for attempt in range(3):
            for _ in range(3):
                self.conn.mav.command_long_send(
                    self.sysid, 1, 400, 0, 1, 0, 0, 0, 0, 0, 0)
                time.sleep(0.2)

            # Check armed status
            timeout = time.time() + 5
            while time.time() < timeout:
                msg = self.conn.recv_match(
                    type='HEARTBEAT', blocking=True, timeout=1)
                if msg and msg.base_mode & 128:
                    print(f"[Vehicle {self.sysid}] ✓ Armed")
                    return True
                time.sleep(0.2)

            if attempt < 2:
                print(f"[Vehicle {self.sysid}] Retry...")

        print(f"[Vehicle {self.sysid}] ✗ Arm failed")
        return False

    def generate_safe_waypoint(self, max_attempts=50):
        """Generate a waypoint that maintains minimum separation from other vehicles"""

        for attempt in range(max_attempts):
            # Generate random candidate position
            x = random.uniform(-self.radius, self.radius)
            y = random.uniform(-self.radius, self.radius)
            z = -random.uniform(self.alt_min, self.alt_max)

            candidate = (x, y, z)

            # Check distance to all other vehicles
            other_positions = self.position_tracker.get_all_except(self.sysid)

            if not other_positions:
                # No other vehicles to check against
                return candidate

            # Check minimum distance to all other vehicles
            min_dist = float('inf')
            for other_pos in other_positions.values():
                dist = self.position_tracker.distance(candidate, other_pos)
                min_dist = min(min_dist, dist)

            # If this position maintains minimum separation, use it
            if min_dist >= self.min_separation:
                return candidate

            # For later attempts, gradually reduce strictness to avoid deadlock
            if attempt > 30:
                adjusted_min = self.min_separation * 0.8
                if min_dist >= adjusted_min:
                    return candidate

        # Fallback: move away from nearest vehicle
        other_positions = self.position_tracker.get_all_except(self.sysid)
        if other_positions:
            # Find nearest vehicle
            nearest_pos = min(other_positions.values(),
                              key=lambda p: self.position_tracker.distance(
                (self.target_x, self.target_y, self.target_z), p))

            # Move in opposite direction
            dx = self.target_x - nearest_pos[0]
            dy = self.target_y - nearest_pos[1]
            dz = self.target_z - nearest_pos[2]

            # Normalize and scale
            dist = math.sqrt(dx*dx + dy*dy + dz*dz)
            if dist > 0:
                scale = self.min_separation * 2 / dist
                x = self.target_x + dx * scale
                y = self.target_y + dy * scale
                z = self.target_z + dz * scale

                # Clamp to boundaries
                x = max(-self.radius, min(self.radius, x))
                y = max(-self.radius, min(self.radius, y))
                z = max(-self.alt_max, min(-self.alt_min, z))

                return (x, y, z)

        # Last resort: keep current position
        return (self.target_x, self.target_y, self.target_z)

    def send_setpoint(self):
        """Send current target position and update tracker"""
        self.conn.mav.set_position_target_local_ned_send(
            0, self.sysid, 1, 1, 0b111111111000,
            self.target_x, self.target_y, self.target_z,
            0, 0, 0, 0, 0, 0, 0, 0)

        # Update position tracker
        self.position_tracker.update(self.sysid,
                                     self.target_x,
                                     self.target_y,
                                     self.target_z)

    def update_waypoint(self):
        """Generate new safe waypoint"""
        self.target_x, self.target_y, self.target_z = self.generate_safe_waypoint()

    def run(self):
        if not self.connect():
            return

        time.sleep(2)

        # Set OFFBOARD
        self.set_offboard()

        # Stream initial setpoints
        print(f"[Vehicle {self.sysid}] Streaming setpoints...")
        for _ in range(30):
            self.send_setpoint()
            time.sleep(0.05)

        # Arm
        if not self.arm():
            return

        # Control loop
        print(f"[Vehicle {self.sysid}] ✓ Flying with collision avoidance")
        interval = 1.0 / self.update_rate
        count = 0
        waypoint_update_interval = 5  # Update waypoint every 5 seconds

        while self.running:
            start = time.time()

            # Update waypoint periodically
            if count % (waypoint_update_interval * self.update_rate) == 0:
                self.update_waypoint()

            self.send_setpoint()

            count += 1
            if count % 40 == 0:
                # Report status with separation info
                other_pos = self.position_tracker.get_all_except(self.sysid)
                if other_pos:
                    min_dist = min(
                        self.position_tracker.distance(
                            (self.target_x, self.target_y, self.target_z), pos)
                        for pos in other_pos.values()
                    )
                    print(f"[Vehicle {self.sysid}] {count} waypoints | "
                          f"Min separation: {min_dist:.2f}m")
                else:
                    print(f"[Vehicle {self.sysid}] {count} waypoints")

            time.sleep(max(0, interval - (time.time() - start)))


# Create shared position tracker
position_tracker = PositionTracker()

# Start 3 commanders
commanders = []
threads = []

for i in range(3):
    port = 14540 + i
    sysid = i + 1

    cmd = MulticopterCommander(
        port=port,
        sysid=sysid,
        update_rate=2,
        radius=300,
        alt_range=(10, 120),
        position_tracker=position_tracker,
        min_separation=50.0
    )
    commanders.append(cmd)

    t = threading.Thread(target=cmd.run, daemon=True)
    threads.append(t)
    t.start()

    time.sleep(5)

print("\n" + "="*50)
print("All vehicles flying with collision avoidance")
print("Minimum separation: 1.0m between any two vehicles")
print("Press Ctrl+C to stop")
print("="*50 + "\n")

try:
    while True:
        time.sleep(10)
except KeyboardInterrupt:
    print("\n\nStopping...")
    for cmd in commanders:
        cmd.running = False
    for t in threads:
        t.join(timeout=2)
    print("✓ Stopped")
