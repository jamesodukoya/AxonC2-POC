"""
Flask + Socket.IO Backend for PX4 Dashboard
Streams real-time telemetry and network metrics to React frontend
Receives ALL PX4 messages, filters to 6 demo messages, tracks full throughput
"""

from flask import Flask, jsonify, request
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import time
import threading
import logging

from mavlink_parser import MAVLinkManager
import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'px4-dashboard-secret-key'

# Configure CORS
cors_origins = "*" if config.CORS_ALLOW_ALL else config.CORS_ALLOWED_ORIGINS
CORS(app, resources={r"/*": {"origins": cors_origins}})

# Initialize Socket.IO
socketio = SocketIO(
    app,
    cors_allowed_origins=cors_origins,
    async_mode='threading',
    logger=True,
    engineio_logger=False
)

# Initialize MAVLink manager
mavlink_manager = MAVLinkManager(config.DRONES)

# Global state
streaming = False
stream_thread = None


@app.route('/')
def index():
    """Health check endpoint"""
    return jsonify({
        "status": "running",
        "drones": len(config.DRONES),
        "streaming": streaming
    })


@app.route('/api/drones')
def get_drones():
    """Get drone configuration"""
    return jsonify({
        "drones": config.DRONES
    })


@app.route('/api/stats')
def get_stats():
    """Get detailed message statistics"""
    return jsonify({
        "stats": mavlink_manager.get_all_detailed_stats()
    })


@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    client_id = request.sid if hasattr(request, 'sid') else 'unknown'
    logger.info(f"✅ Client connected: {client_id}")
    logger.info(f"   Total connected clients: {len(socketio.server.manager.rooms.get('/', {}))}")
    
    response = {
        'status': 'connected',
        'drones': config.DRONES,
        'server_time': time.time()
    }
    emit('connection_response', response)
    logger.debug(f"📤 Sent connection_response to client {client_id}")


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    client_id = request.sid if hasattr(request, 'sid') else 'unknown'
    logger.info(f"❌ Client disconnected: {client_id}")
    logger.info(f"   Remaining connected clients: {len(socketio.server.manager.rooms.get('/', {}))}")


@socketio.on('start_streaming')
def handle_start_streaming():
    """Start telemetry streaming"""
    global streaming, stream_thread
    
    client_id = request.sid if hasattr(request, 'sid') else 'unknown'
    logger.info(f"▶️  Client {client_id} requested streaming start")

    if not streaming:
        streaming = True
        stream_thread = threading.Thread(
            target=telemetry_stream_loop, daemon=True)
        stream_thread.start()
        logger.info("🎬 Telemetry streaming thread started")
        emit('streaming_status', {'streaming': True})
    else:
        logger.info("⚠️  Streaming already active")
        emit('streaming_status', {'streaming': True})


@socketio.on('stop_streaming')
def handle_stop_streaming():
    """Stop telemetry streaming"""
    global streaming
    
    client_id = request.sid if hasattr(request, 'sid') else 'unknown'
    logger.info(f"⏸️  Client {client_id} requested streaming stop")
    
    streaming = False
    logger.info("🛑 Telemetry streaming stopped")
    emit('streaming_status', {'streaming': False})


@socketio.on('request_stats')
def handle_request_stats():
    """Send detailed statistics on request"""
    stats = mavlink_manager.get_all_detailed_stats()
    emit('stats_update', stats)


def telemetry_stream_loop():
    """Main loop for streaming telemetry data - WITH DEBUGGING"""
    update_interval = 1.0 / config.TELEMETRY_UPDATE_HZ
    iteration_count = 0
    last_debug_time = time.time()

    logger.info(f"🎬 Telemetry stream started - Update rate: {config.TELEMETRY_UPDATE_HZ} Hz")

    while streaming:
        try:
            iteration_count += 1
            current_time = time.time()
            
            # Debug logging every 30 seconds
            if current_time - last_debug_time >= 30:
                logger.info(f"📊 Stream alive - Iteration {iteration_count}, Uptime: {int(current_time - last_debug_time)}s")
                last_debug_time = current_time

            # Get all telemetry and metrics
            telemetry_data = mavlink_manager.get_all_telemetry()
            metrics_data = mavlink_manager.get_all_metrics()

            # 🐛 DEBUG: Log what we got
            logger.debug(f"📥 Retrieved telemetry for {len(telemetry_data)} drones")
            
            for drone_id in telemetry_data.keys():
                telemetry = telemetry_data[drone_id]
                logger.debug(f"  Drone {drone_id}: connected={telemetry.get('connected')}, "
                           f"last_update={telemetry.get('last_update')}")

            # Combine into single update
            update = {
                'timestamp': time.time(),
                'drones': []
            }

            for drone_id in telemetry_data.keys():
                telemetry = telemetry_data[drone_id]
                metrics = metrics_data[drone_id]

                # 🐛 DEBUG: Log detailed telemetry state
                logger.debug(f"🔍 Processing Drone {drone_id} ({telemetry['name']}):")
                logger.debug(f"    Connected: {telemetry['connected']}")
                logger.debug(f"    Has GPS: {telemetry.get('gps') is not None}")
                logger.debug(f"    Has Position: {telemetry.get('position') is not None}")
                logger.debug(f"    Has Battery: {telemetry.get('battery') is not None}")
                logger.debug(f"    Has Heartbeat: {telemetry.get('heartbeat') is not None}")
                logger.debug(f"    Demo packets: {metrics.get('demo_packet_count')}")
                logger.debug(f"    Total packets: {metrics.get('total_packet_count')}")

                # Build comprehensive drone state
                drone_state = {
                    'id': drone_id,
                    'name': telemetry['name'],
                    'color': telemetry['color'],
                    'connected': telemetry['connected'],

                    # Position data (for map)
                    'position': None,

                    # Telemetry
                    'battery_percent': None,
                    'battery_voltage': None,
                    'altitude': None,
                    'ground_speed': None,
                    'heading': None,
                    'satellites': None,
                    'gps_fix': None,

                    # Network metrics (demo messages only)
                    'latency_ms': metrics.get('latency_ms'),
                    'jitter_ms': metrics.get('jitter_ms'),
                    # Rate of demo messages sent to frontend
                    'update_rate_hz': metrics.get('demo_rate_hz'),
                    # Demo messages only
                    'packet_count': metrics.get('demo_packet_count'),

                    # Throughput metrics (ALL PX4 messages received)
                    # Total incoming message rate
                    'total_rate_hz': metrics.get('total_rate_hz'),
                    # All messages received
                    'total_packet_count': metrics.get('total_packet_count'),
                    # Messages filtered out
                    'filtered_packet_count': metrics.get('filtered_packet_count'),
                    # Total unique message types
                    'total_message_types': metrics.get('total_message_types'),
                    # Demo message types (should be 6)
                    'demo_message_types': metrics.get('demo_message_types'),

                    # Status
                    'status': 'Unknown',
                    'mode': 'Unknown'
                }

                # Extract position from GPS or GLOBAL_POSITION_INT
                if telemetry.get('position'):
                    drone_state['position'] = {
                        'lat': telemetry['position']['lat'],
                        'lon': telemetry['position']['lon'],
                        'alt': telemetry['position']['alt']
                    }
                    drone_state['altitude'] = telemetry['position']['relative_alt']
                    logger.debug(f"    ✓ Position from GLOBAL_POSITION_INT: {drone_state['position']['lat']:.6f}, {drone_state['position']['lon']:.6f}")
                elif telemetry.get('gps'):
                    drone_state['position'] = {
                        'lat': telemetry['gps']['lat'],
                        'lon': telemetry['gps']['lon'],
                        'alt': telemetry['gps']['alt']
                    }
                    drone_state['altitude'] = telemetry['gps']['alt']
                    logger.debug(f"    ✓ Position from GPS_RAW_INT: {drone_state['position']['lat']:.6f}, {drone_state['position']['lon']:.6f}")
                else:
                    logger.debug(f"    ✗ No position data available")

                # Extract battery info
                if telemetry.get('battery'):
                    drone_state['battery_percent'] = telemetry['battery']['battery_remaining']
                    drone_state['battery_voltage'] = telemetry['battery']['voltage']
                    logger.debug(f"    ✓ Battery: {drone_state['battery_percent']}% @ {drone_state['battery_voltage']}V")
                else:
                    logger.debug(f"    ✗ No battery data")

                # Extract GPS info
                if telemetry.get('gps'):
                    drone_state['satellites'] = telemetry['gps']['satellites_visible']
                    drone_state['gps_fix'] = telemetry['gps']['fix_type']
                    logger.debug(f"    ✓ GPS: {drone_state['satellites']} sats, fix type {drone_state['gps_fix']}")
                else:
                    logger.debug(f"    ✗ No GPS data")

                # Extract speed and heading
                if telemetry.get('vfr_hud'):
                    drone_state['ground_speed'] = telemetry['vfr_hud']['groundspeed']
                    drone_state['heading'] = telemetry['vfr_hud']['heading']
                    logger.debug(f"    ✓ VFR_HUD: {drone_state['ground_speed']} m/s @ {drone_state['heading']}°")
                elif telemetry.get('gps'):
                    drone_state['ground_speed'] = telemetry['gps']['vel']
                    drone_state['heading'] = telemetry['gps']['cog']
                    logger.debug(f"    ✓ GPS velocity: {drone_state['ground_speed']} m/s @ {drone_state['heading']}°")
                else:
                    logger.debug(f"    ✗ No velocity data")

                # Extract system status
                if telemetry.get('heartbeat'):
                    status_codes = {
                        0: 'Uninit',
                        1: 'Boot',
                        2: 'Calibrating',
                        3: 'Standby',
                        4: 'Active',
                        5: 'Critical',
                        6: 'Emergency',
                        7: 'Poweroff',
                        8: 'Flight Termination'
                    }
                    drone_state['status'] = status_codes.get(
                        telemetry['heartbeat']['system_status'],
                        'Unknown'
                    )
                    logger.debug(f"    ✓ Status: {drone_state['status']}")
                else:
                    logger.debug(f"    ✗ No heartbeat")

                update['drones'].append(drone_state)

            # 🐛 DEBUG: Log what we're emitting
            logger.debug(f"📤 Emitting update with {len(update['drones'])} drones")
            for drone in update['drones']:
                logger.debug(f"    Drone {drone['id']}: connected={drone['connected']}, "
                           f"position={'Yes' if drone['position'] else 'No'}, "
                           f"battery={drone['battery_percent']}, "
                           f"packets={drone['packet_count']}")

            # Emit to all connected clients
            socketio.emit('telemetry_update', update)
            logger.debug(f"✅ Telemetry update emitted successfully")

            # Sleep until next update
            time.sleep(update_interval)

        except Exception as e:
            logger.error(f"❌ Error in telemetry stream: {e}", exc_info=True)
            time.sleep(1)


def initialize_mavlink():
    """Initialize MAVLink connections in background"""
    def connect():
        logger.info("Connecting to PX4 instances...")
        mavlink_manager.connect_all()
        logger.info("MAVLink initialization complete")

        # Print initial stats after 5 seconds
        time.sleep(5)
        logger.info("\n" + "="*80)
        logger.info("Initial Message Statistics:")
        logger.info("="*80)
        mavlink_manager.print_stats()

    init_thread = threading.Thread(target=connect, daemon=True)
    init_thread.start()


def periodic_stats_logger():
    """Periodically log statistics"""
    while True:
        time.sleep(30)  # Log every 30 seconds
        if streaming:
            logger.info("\n" + "-"*80)
            logger.info("Periodic Statistics Update:")
            logger.info("-"*80)
            mavlink_manager.print_stats()


if __name__ == '__main__':
    logger.info("=" * 60)
    logger.info("PX4 Command & Control Dashboard Backend")
    logger.info("MESSAGE FILTERING ENABLED")
    logger.info("=" * 60)
    logger.info(f"Configured drones: {len(config.DRONES)}")
    for drone in config.DRONES:
        logger.info(f"  - {drone['name']}: {drone['host']}:{drone['port']}")
    logger.info(f"Update rate: {config.TELEMETRY_UPDATE_HZ} Hz")
    logger.info("")
    logger.info(
        "Mode: Receiving ALL PX4 messages, forwarding only 6 demo messages")
    logger.info("Demo messages: HEARTBEAT, GPS_RAW_INT, GLOBAL_POSITION_INT,")
    logger.info("               BATTERY_STATUS, ATTITUDE, VFR_HUD")
    logger.info("Throughput: Calculated from ALL received messages")
    logger.info("=" * 60)

    # Initialize MAVLink connections
    initialize_mavlink()

    # Start periodic stats logger
    stats_thread = threading.Thread(target=periodic_stats_logger, daemon=True)
    stats_thread.start()

    # Start Flask-SocketIO server
    logger.info(f"Starting server on {config.HOST}:{config.PORT}")
    socketio.run(
        app,
        host=config.HOST,
        port=config.PORT,
        debug=config.DEBUG,
        allow_unsafe_werkzeug=True
    )
