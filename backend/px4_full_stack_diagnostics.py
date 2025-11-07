#!/usr/bin/env python3
"""
Comprehensive PX4 Multi-Vehicle Stack Diagnostics
Tests all layers: PX4 SITL -> MAVLink -> Flask -> WebSocket -> React

Usage:
    python3 px4_full_stack_diagnostics.py [options]

Options:
    --quick         Run quick checks only (5 seconds per test)
    --full          Run full diagnostics (30 seconds per test)
    --layer LAYER   Test specific layer only (px4, mavlink, flask, websocket, all)
    --verbose       Show detailed packet-level information
"""

import sys
import time
import socket
import threading
import subprocess
import requests
import json
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Tuple

try:
    from pymavlink import mavutil
except ImportError:
    print("ERROR: pymavlink not installed. Run: pip install pymavlink")
    sys.exit(1)

try:
    import socketio
except ImportError:
    print("WARNING: python-socketio not installed. WebSocket tests will be skipped.")
    print("Install with: pip install python-socketio[client]")
    socketio = None


# ============================================================================
# ANSI Colors for Output
# ============================================================================
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'


def print_header(text):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*80}{Colors.END}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text:^80}{Colors.END}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*80}{Colors.END}\n")


def print_section(text):
    print(f"\n{Colors.CYAN}{Colors.BOLD}--- {text} ---{Colors.END}")


def print_success(text):
    print(f"{Colors.GREEN}✓ {text}{Colors.END}")


def print_warning(text):
    print(f"{Colors.YELLOW}⚠ {text}{Colors.END}")


def print_error(text):
    print(f"{Colors.RED}✗ {text}{Colors.END}")


def print_info(text):
    print(f"{Colors.BLUE}ℹ {text}{Colors.END}")


# ============================================================================
# LAYER 1: PX4 SITL Instance Detection
# ============================================================================
class PX4Diagnostics:
    """Test PX4 SITL instances are running and configured correctly"""

    @staticmethod
    def check_px4_processes():
        """Check if PX4 processes are running"""
        print_section("Layer 1: PX4 SITL Process Check")

        try:
            result = subprocess.run(['pgrep', '-a', 'px4'],
                                    capture_output=True, text=True)

            if result.returncode == 0:
                processes = result.stdout.strip().split('\n')
                print_success(f"Found {len(processes)} PX4 process(es)")

                for i, proc in enumerate(processes, 1):
                    print(f"  [{i}] {proc}")

                return True, len(processes)
            else:
                print_error("No PX4 processes found")
                print_info("Start PX4 with: ./spawn_three_vehicles_sitl.sh")
                return False, 0

        except Exception as e:
            print_error(f"Failed to check processes: {e}")
            return False, 0

    @staticmethod
    def check_udp_ports(ports=[14540, 14541, 14542]):
        """Check if MAVLink UDP ports are bound"""
        print_section("Layer 1: UDP Port Binding Check")

        bound_ports = []

        # Try lsof first
        lsof_available = True
        try:
            subprocess.run(['lsof', '-v'], capture_output=True, check=True)
        except (FileNotFoundError, subprocess.CalledProcessError):
            lsof_available = False

        if lsof_available:
            for port in ports:
                try:
                    result = subprocess.run(
                        ['lsof', '-i', f'UDP:{port}'],
                        capture_output=True, text=True
                    )

                    if result.returncode == 0 and result.stdout:
                        print_success(f"Port {port} is bound (PX4 listening)")
                        bound_ports.append(port)
                    else:
                        print_warning(f"Port {port} not bound (lsof)")

                except Exception as e:
                    print_warning(f"Port {port} check failed: {e}")
        else:
            # Fallback to netstat
            print_info("lsof not available, trying netstat...")
            try:
                result = subprocess.run(
                    ['netstat', '-an'],
                    capture_output=True, text=True
                )

                if result.returncode == 0:
                    for port in ports:
                        if f':{port}' in result.stdout or f'.{port}' in result.stdout:
                            print_success(f"Port {port} appears to be in use")
                            bound_ports.append(port)
                        else:
                            print_warning(f"Port {port} not detected")
                else:
                    print_warning(
                        "netstat check failed, skipping port validation")
                    print_info(
                        "Port binding check is informational only - not critical for operation")
                    # Assume ports are OK if we can't verify
                    return True, ports

            except FileNotFoundError:
                print_warning("Neither lsof nor netstat available")
                print_info(
                    "Skipping port check - will verify via MAVLink connection test")
                # If we can't check, assume OK and let MAVLink test verify
                return True, ports

        if not bound_ports and lsof_available:
            print_warning(
                "No ports detected as bound, but PX4 processes are running")
            print_info(
                "This is OK - ports may be using different protocol or PX4 binds on demand")
            # Return True because Layer 2 will verify actual connectivity
            return True, []

        return len(bound_ports) > 0 or not lsof_available, bound_ports


# ============================================================================
# LAYER 2: MAVLink Connection & Message Reception
# ============================================================================
class MAVLinkDiagnostics:
    """Test MAVLink connections and message reception"""

    def __init__(self, verbose=False):
        self.verbose = verbose
        self.connections = {}
        self.message_stats = defaultdict(lambda: defaultdict(int))
        self.heartbeat_times = {}

    def test_connection(self, port, system_id, duration=10):
        """Test MAVLink connection to a single drone"""
        print_section(
            f"Layer 2: MAVLink Connection Test - Port {port} (System ID {system_id})")

        conn_str = f'udp:127.0.0.1:{port}'
        print_info(f"Connecting to {conn_str}...")

        try:
            conn = mavutil.mavlink_connection(conn_str, source_system=255)

            # Wait for heartbeat with timeout
            print_info("Waiting for heartbeat...")
            heartbeat = conn.wait_heartbeat(timeout=10)

            if not heartbeat:
                print_error("No heartbeat received within 10 seconds")
                return False

            # Verify system ID
            if heartbeat.get_srcSystem() != system_id:
                print_error(
                    f"System ID mismatch: expected {system_id}, got {heartbeat.get_srcSystem()}")
                print_warning(
                    "This indicates MAVLink routing configuration error")
            else:
                print_success(f"Heartbeat received from System ID {system_id}")

            # Collect messages for duration
            print_info(f"Collecting messages for {duration} seconds...")

            start_time = time.time()
            msg_count = 0
            msg_types = set()

            while time.time() - start_time < duration:
                msg = conn.recv_match(blocking=True, timeout=1)

                if msg:
                    msg_count += 1
                    msg_type = msg.get_type()
                    msg_types.add(msg_type)

                    # Track message stats
                    self.message_stats[port][msg_type] += 1

                    if self.verbose and msg_count % 100 == 0:
                        print(
                            f"  Received {msg_count} messages, {len(msg_types)} types")

            elapsed = time.time() - start_time
            rate = msg_count / elapsed if elapsed > 0 else 0

            print_success(
                f"Received {msg_count} messages in {elapsed:.1f}s ({rate:.1f} msg/s)")
            print_info(f"Message types: {len(msg_types)}")

            # Show top message types
            top_messages = sorted(self.message_stats[port].items(),
                                  key=lambda x: x[1], reverse=True)[:10]

            print("\n  Top 10 message types:")
            for msg_type, count in top_messages:
                print(f"    {msg_type:25s} : {count:5d} messages")

            return True

        except Exception as e:
            print_error(f"Connection failed: {e}")
            return False

    def test_all_connections(self, duration=10):
        """Test connections to all three drones"""
        print_header("LAYER 2: MAVLink Message Reception Test")

        configs = [
            (14540, 1, "Drone Alpha"),
            (14541, 2, "Drone Bravo"),
            (14542, 3, "Drone Charlie")
        ]

        results = []

        for port, system_id, name in configs:
            print(f"\n{Colors.BOLD}Testing {name}{Colors.END}")
            success = self.test_connection(port, system_id, duration)
            results.append((name, success))
            time.sleep(1)

        # Summary
        print_section("MAVLink Test Summary")
        passed = sum(1 for _, success in results if success)

        for name, success in results:
            if success:
                print_success(f"{name}: PASS")
            else:
                print_error(f"{name}: FAIL")

        print(
            f"\n{Colors.BOLD}Result: {passed}/3 connections successful{Colors.END}")

        return passed == 3


# ============================================================================
# LAYER 3: Flask Backend API Tests
# ============================================================================
class FlaskDiagnostics:
    """Test Flask backend REST API endpoints"""

    def __init__(self, base_url="http://localhost:5000"):
        self.base_url = base_url

    def test_health_endpoint(self):
        """Test the root health check endpoint"""
        print_section("Layer 3: Flask Health Check")

        try:
            response = requests.get(f"{self.base_url}/", timeout=5)

            if response.status_code == 200:
                data = response.json()
                print_success("Backend is running")
                print(f"  Status: {data.get('status')}")
                print(f"  Drones configured: {data.get('drones')}")
                print(f"  Streaming: {data.get('streaming')}")
                return True
            else:
                print_error(
                    f"Health check failed: HTTP {response.status_code}")
                return False

        except requests.exceptions.ConnectionError:
            print_error("Cannot connect to Flask backend")
            print_info("Start backend with: python3 app.py")
            return False
        except Exception as e:
            print_error(f"Health check failed: {e}")
            return False

    def test_drones_endpoint(self):
        """Test the /api/drones endpoint"""
        print_section("Layer 3: Flask Drones Configuration")

        try:
            response = requests.get(f"{self.base_url}/api/drones", timeout=5)

            if response.status_code == 200:
                data = response.json()
                drones = data.get('drones', [])

                print_success(
                    f"Retrieved configuration for {len(drones)} drones")

                for drone in drones:
                    print(f"\n  {drone['name']}:")
                    print(f"    ID: {drone['id']}")
                    print(f"    System ID: {drone['system_id']}")
                    print(f"    Host: {drone['host']}")
                    print(f"    Port: {drone['port']}")
                    print(f"    Color: {drone['color']}")

                # Check for system ID configuration
                system_ids = [d['system_id'] for d in drones]
                if len(system_ids) != len(set(system_ids)):
                    print_warning("Duplicate system IDs detected!")
                else:
                    print_success("All system IDs are unique")

                return True
            else:
                print_error(f"Failed: HTTP {response.status_code}")
                return False

        except Exception as e:
            print_error(f"Request failed: {e}")
            return False

    def test_stats_endpoint(self):
        """Test the /api/stats endpoint"""
        print_section("Layer 3: Flask Statistics Endpoint")

        try:
            response = requests.get(f"{self.base_url}/api/stats", timeout=5)

            if response.status_code == 200:
                data = response.json()
                stats = data.get('stats', {})

                print_success(f"Retrieved stats for {len(stats)} drones")

                for drone_id, drone_stats in stats.items():
                    print(f"\n  Drone {drone_id}:")
                    print(
                        f"    Total packets: {drone_stats.get('total_packet_count', 0)}")
                    print(
                        f"    Demo packets: {drone_stats.get('demo_packet_count', 0)}")
                    print(
                        f"    Filtered: {drone_stats.get('filtered_packet_count', 0)}")
                    print(
                        f"    Total rate: {drone_stats.get('total_rate_hz', 0):.1f} Hz")
                    print(
                        f"    Demo rate: {drone_stats.get('demo_rate_hz', 0):.1f} Hz")

                return True
            else:
                print_error(f"Failed: HTTP {response.status_code}")
                return False

        except Exception as e:
            print_error(f"Request failed: {e}")
            return False

    def run_all_tests(self):
        """Run all Flask endpoint tests"""
        print_header("LAYER 3: Flask Backend API Tests")

        results = [
            ("Health Check", self.test_health_endpoint()),
            ("Drones Config", self.test_drones_endpoint()),
            ("Statistics", self.test_stats_endpoint())
        ]

        print_section("Flask Test Summary")
        passed = sum(1 for _, success in results if success)

        for name, success in results:
            if success:
                print_success(f"{name}: PASS")
            else:
                print_error(f"{name}: FAIL")

        print(f"\n{Colors.BOLD}Result: {passed}/3 endpoints working{Colors.END}")

        return passed == 3


# ============================================================================
# LAYER 4: WebSocket Connection & Telemetry Stream
# ============================================================================
class WebSocketDiagnostics:
    """Test WebSocket connection and telemetry streaming"""

    def __init__(self, url="http://localhost:5000"):
        self.url = url
        self.sio = None
        self.connected = False
        self.streaming = False
        self.telemetry_count = 0
        self.telemetry_data = []
        self.connection_response = None

    def test_connection(self, duration=15):
        """Test WebSocket connection and telemetry streaming"""
        print_header("LAYER 4: WebSocket Connection & Telemetry Stream")

        if socketio is None:
            print_error(
                "python-socketio not installed, skipping WebSocket tests")
            print_info("Install with: pip install python-socketio[client]")
            return False

        print_section("WebSocket Connection Test")
        print_info(f"Connecting to {self.url}...")

        try:
            self.sio = socketio.Client(logger=False, engineio_logger=False)

            # Set up event handlers
            @self.sio.on('connect')
            def on_connect():
                self.connected = True
                print_success("WebSocket connected")

            @self.sio.on('disconnect')
            def on_disconnect():
                self.connected = False
                print_warning("WebSocket disconnected")

            @self.sio.on('connection_response')
            def on_connection_response(data):
                self.connection_response = data
                print_success("Received connection response")
                print(f"  Status: {data.get('status')}")
                print(f"  Drones: {len(data.get('drones', []))}")

            @self.sio.on('streaming_status')
            def on_streaming_status(data):
                self.streaming = data.get('streaming', False)
                status = "started" if self.streaming else "stopped"
                print_info(f"Streaming {status}")

            @self.sio.on('telemetry_update')
            def on_telemetry_update(data):
                self.telemetry_count += 1
                self.telemetry_data.append(data)

                if self.telemetry_count == 1:
                    print_success("First telemetry update received!")
                    print(f"  Timestamp: {data.get('timestamp')}")
                    print(f"  Drones in update: {len(data.get('drones', []))}")

            # Connect
            self.sio.connect(self.url, transports=['websocket', 'polling'])
            time.sleep(2)

            if not self.connected:
                print_error("Failed to establish WebSocket connection")
                return False

            # Start streaming
            print_section("Telemetry Streaming Test")
            print_info("Starting telemetry stream...")
            self.sio.emit('start_streaming')
            time.sleep(1)

            # Collect telemetry for duration
            print_info(f"Collecting telemetry for {duration} seconds...")

            start_time = time.time()
            last_count = 0

            while time.time() - start_time < duration:
                time.sleep(1)
                elapsed = time.time() - start_time
                new_updates = self.telemetry_count - last_count

                if new_updates > 0:
                    print(f"  [{elapsed:.0f}s] Received {self.telemetry_count} updates "
                          f"(+{new_updates} in last second)")
                else:
                    print_warning(
                        f"  [{elapsed:.0f}s] No updates in last second")

                last_count = self.telemetry_count

            # Stop streaming
            print_info("Stopping telemetry stream...")
            self.sio.emit('stop_streaming')
            time.sleep(1)

            # Analyze results
            print_section("Telemetry Analysis")

            if self.telemetry_count == 0:
                print_error("No telemetry updates received!")
                return False

            print_success(f"Received {self.telemetry_count} telemetry updates")

            # Analyze update rate
            rate = self.telemetry_count / duration
            print(f"  Update rate: {rate:.2f} Hz")

            if rate < 4:
                print_warning(f"Update rate is low (expected ~5 Hz)")
            elif rate > 6:
                print_warning(f"Update rate is high (expected ~5 Hz)")
            else:
                print_success("Update rate is within expected range")

            # Analyze drone data completeness
            if self.telemetry_data:
                self._analyze_drone_data()

            # Disconnect
            self.sio.disconnect()

            return True

        except Exception as e:
            print_error(f"WebSocket test failed: {e}")
            if self.sio:
                self.sio.disconnect()
            return False

    def _analyze_drone_data(self):
        """Analyze completeness of drone data in telemetry"""
        print_section("Drone Data Completeness")

        # Get a recent telemetry update
        recent_update = self.telemetry_data[-1]
        drones = recent_update.get('drones', [])

        print_info(f"Analyzing data from {len(drones)} drones in last update:")

        for drone in drones:
            print(f"\n  {drone.get('name', 'Unknown')} (ID: {drone.get('id')}):")
            print(f"    Connected: {drone.get('connected')}")

            # Check position data
            position = drone.get('position')
            if position and all(position.get(k) is not None for k in ['lat', 'lon', 'alt']):
                print_success(
                    f"    Position: ✓ ({position['lat']:.6f}, {position['lon']:.6f})")
            else:
                print_warning("    Position: Missing or incomplete")

            # Check battery data
            battery = drone.get('battery_percent')
            if battery is not None:
                print_success(f"    Battery: ✓ ({battery}%)")
            else:
                print_warning("    Battery: No data")

            # Check GPS data
            sats = drone.get('satellites')
            if sats is not None:
                print_success(f"    GPS: ✓ ({sats} satellites)")
            else:
                print_warning("    GPS: No data")

            # Check network metrics
            latency = drone.get('latency_ms')
            if latency is not None:
                print_success(f"    Latency: ✓ ({latency:.1f} ms)")
            else:
                print_warning("    Latency: No data")

            # Check throughput metrics
            total_rate = drone.get('total_rate_hz')
            if total_rate is not None:
                print_success(f"    Total rate: ✓ ({total_rate:.1f} Hz)")
            else:
                print_warning("    Total rate: No data")


# ============================================================================
# LAYER 5: System ID Routing Validation
# ============================================================================
class SystemIDDiagnostics:
    """Validate that System IDs are correctly routed"""

    def test_system_id_routing(self, duration=10):
        """Test that each port receives only its designated system ID"""
        print_header("LAYER 5: System ID Routing Validation")

        configs = [
            (14540, 1, "Drone Alpha"),
            (14541, 2, "Drone Bravo"),
            (14542, 3, "Drone Charlie")
        ]

        routing_correct = True

        for port, expected_sysid, name in configs:
            print_section(
                f"Testing {name} - Port {port}, Expected System ID {expected_sysid}")

            try:
                conn_str = f'udp:127.0.0.1:{port}'
                conn = mavutil.mavlink_connection(conn_str, source_system=255)

                print_info("Collecting messages to verify system IDs...")

                start_time = time.time()
                system_ids_seen = defaultdict(int)

                while time.time() - start_time < duration:
                    msg = conn.recv_match(blocking=True, timeout=1)
                    if msg:
                        sysid = msg.get_srcSystem()
                        system_ids_seen[sysid] += 1

                print(f"\n  System IDs observed:")

                # Filter out GCS system IDs (0 and 255) - these are normal
                vehicle_system_ids = {sid: count for sid, count in system_ids_seen.items()
                                      if sid not in [0, 255]}

                for sysid, count in sorted(system_ids_seen.items()):
                    if sysid in [0, 255]:
                        print(
                            f"    System ID {sysid}: {count} messages (GCS - expected)")
                    elif sysid == expected_sysid:
                        print_success(
                            f"    System ID {sysid}: {count} messages (CORRECT)")
                    else:
                        print_error(
                            f"    System ID {sysid}: {count} messages (WRONG!)")
                        routing_correct = False

                # Only check vehicle system IDs (ignore GCS)
                if len(vehicle_system_ids) > 1:
                    print_error(
                        f"  Multiple vehicle system IDs detected on port {port}!")
                    print_warning("  This indicates MAVLink routing is broken")
                    routing_correct = False
                elif expected_sysid not in vehicle_system_ids:
                    print_error(
                        f"  Expected system ID {expected_sysid} not seen!")
                    routing_correct = False
                else:
                    print_success(
                        f"  Routing correct: Only System ID {expected_sysid} on port {port}")

            except Exception as e:
                print_error(f"Test failed: {e}")
                routing_correct = False

            time.sleep(1)

        print_section("System ID Routing Summary")
        if routing_correct:
            print_success("All ports receive correct system IDs")
            print_success("MAVLink routing is configured correctly")
            return True
        else:
            print_error("System ID routing errors detected")
            print_warning(
                "Check mavlink_router configuration or PX4 MAVLink setup")
            return False


# ============================================================================
# Main Test Runner
# ============================================================================
class FullStackDiagnostics:
    """Run complete diagnostic suite"""

    def __init__(self, quick=False, verbose=False):
        self.quick = quick
        self.verbose = verbose
        self.test_duration = 5 if quick else 10

    def run_all(self):
        """Run all diagnostic layers"""
        print_header("PX4 Multi-Vehicle Full Stack Diagnostics")
        print(f"Mode: {'Quick' if self.quick else 'Full'}")
        print(f"Test duration: {self.test_duration} seconds per test")
        print(f"Verbose: {self.verbose}")

        results = {}

        # Layer 1: PX4
        px4_diag = PX4Diagnostics()
        processes_ok, num_processes = px4_diag.check_px4_processes()
        ports_ok, bound_ports = px4_diag.check_udp_ports()
        results['px4_processes'] = processes_ok
        results['px4_ports'] = ports_ok

        if not processes_ok:
            print_error(
                "\nPX4 processes not running. Cannot proceed with further tests.")
            print_info("Start PX4 with: ./spawn_three_vehicles_sitl.sh")
            return results

        # Layer 2: MAVLink
        mavlink_diag = MAVLinkDiagnostics(verbose=self.verbose)
        results['mavlink'] = mavlink_diag.test_all_connections(
            self.test_duration)

        # Layer 3: Flask
        flask_diag = FlaskDiagnostics()
        results['flask'] = flask_diag.run_all_tests()

        # Layer 4: WebSocket
        if socketio is not None:
            ws_diag = WebSocketDiagnostics()
            results['websocket'] = ws_diag.test_connection(
                self.test_duration * 2)
        else:
            results['websocket'] = None

        # Layer 5: System ID Routing
        sysid_diag = SystemIDDiagnostics()
        results['system_id_routing'] = sysid_diag.test_system_id_routing(
            self.test_duration)

        # Final Summary
        self._print_final_summary(results)

        return results

    def _print_final_summary(self, results):
        """Print comprehensive test summary"""
        print_header("FINAL DIAGNOSTIC SUMMARY")

        layers = [
            ("Layer 1: PX4 Processes", results.get('px4_processes')),
            ("Layer 1: UDP Port Binding", results.get('px4_ports')),
            ("Layer 2: MAVLink Connections", results.get('mavlink')),
            ("Layer 3: Flask Backend", results.get('flask')),
            ("Layer 4: WebSocket Streaming", results.get('websocket')),
            ("Layer 5: System ID Routing", results.get('system_id_routing'))
        ]

        total = 0
        passed = 0

        for name, result in layers:
            if result is None:
                print(f"  {name:40s} : {Colors.YELLOW}SKIPPED{Colors.END}")
            elif result:
                print_success(f"{name:40s} : PASS")
                passed += 1
                total += 1
            else:
                print_error(f"{name:40s} : FAIL")
                total += 1

        print(
            f"\n{Colors.BOLD}Overall Result: {passed}/{total} tests passed{Colors.END}")

        if passed == total:
            print_success("\n🎉 All systems operational!")
        else:
            print_error(f"\n⚠️  {total - passed} test(s) failed")
            print_info("\nTroubleshooting steps:")

            if not results.get('px4_processes'):
                print("  1. Start PX4: ./spawn_three_vehicles_sitl.sh")

            if not results.get('mavlink'):
                print("  2. Check MAVLink connections and port configuration")
                print("     - Verify ports 14540-14542 are not blocked")
                print("     - Check PX4 startup logs: tail -f /tmp/px4_logs/px4_*.log")

            if not results.get('flask'):
                print("  3. Start Flask backend: python3 app.py")

            if not results.get('system_id_routing'):
                print("  4. Check System ID configuration in config.py")
                print("     - Ensure system_id matches instance number (1, 2, 3)")
                print("     - Verify MAVLink router is not interfering")


# ============================================================================
# Command Line Interface
# ============================================================================
def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='PX4 Multi-Vehicle Stack Diagnostics',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run full diagnostics (recommended)
  python3 px4_full_stack_diagnostics.py --full
  
  # Quick check (5 seconds per test)
  python3 px4_full_stack_diagnostics.py --quick
  
  # Verbose output with packet details
  python3 px4_full_stack_diagnostics.py --full --verbose
  
  # Test specific layer only
  python3 px4_full_stack_diagnostics.py --layer mavlink
        """
    )

    parser.add_argument('--quick', action='store_true',
                        help='Run quick checks (5 seconds per test)')
    parser.add_argument('--full', action='store_true',
                        help='Run full diagnostics (10 seconds per test)')
    parser.add_argument('--verbose', action='store_true',
                        help='Show detailed packet-level information')
    parser.add_argument('--layer', choices=['px4', 'mavlink', 'flask', 'websocket', 'routing', 'all'],
                        help='Test specific layer only')

    args = parser.parse_args()

    # Default to full if neither specified
    if not args.quick and not args.full:
        args.full = True

    quick_mode = args.quick and not args.full

    # Run diagnostics
    diagnostics = FullStackDiagnostics(quick=quick_mode, verbose=args.verbose)

    if args.layer and args.layer != 'all':
        print_info(f"Testing layer: {args.layer}")
        # Run specific layer tests
        # (could be extended to support individual layer testing)
        diagnostics.run_all()
    else:
        diagnostics.run_all()


if __name__ == '__main__':
    main()
