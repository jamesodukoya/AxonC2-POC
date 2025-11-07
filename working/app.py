"""
Flask + Socket.IO Backend for PX4 Dashboard
Streams real-time telemetry and network metrics to React frontend
"""

from flask import Flask, jsonify
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


@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    logger.info(
        f"Client connected: {request.sid if 'request' in dir() else 'unknown'}")
    emit('connection_response', {
        'status': 'connected',
        'drones': config.DRONES
    })


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    logger.info("Client disconnected")


@socketio.on('start_streaming')
def handle_start_streaming():
    """Start telemetry streaming"""
    global streaming, stream_thread

    if not streaming:
        streaming = True
        stream_thread = threading.Thread(
            target=telemetry_stream_loop, daemon=True)
        stream_thread.start()
        logger.info("Telemetry streaming started")
        emit('streaming_status', {'streaming': True})


@socketio.on('stop_streaming')
def handle_stop_streaming():
    """Stop telemetry streaming"""
    global streaming
    streaming = False
    logger.info("Telemetry streaming stopped")
    emit('streaming_status', {'streaming': False})


def telemetry_stream_loop():
    """Main loop for streaming telemetry data"""
    update_interval = 1.0 / config.TELEMETRY_UPDATE_HZ

    while streaming:
        try:
            # Get all telemetry and metrics
            telemetry_data = mavlink_manager.get_all_telemetry()
            metrics_data = mavlink_manager.get_all_metrics()

            # Combine into single update
            update = {
                'timestamp': time.time(),
                'drones': []
            }

            for drone_id in telemetry_data.keys():
                telemetry = telemetry_data[drone_id]
                metrics = metrics_data[drone_id]

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

                    # Network metrics
                    'latency_ms': metrics.get('latency_ms'),
                    'jitter_ms': metrics.get('jitter_ms'),
                    'update_rate_hz': metrics.get('update_rate_hz'),
                    'packet_count': metrics.get('packet_count'),

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
                elif telemetry.get('gps'):
                    drone_state['position'] = {
                        'lat': telemetry['gps']['lat'],
                        'lon': telemetry['gps']['lon'],
                        'alt': telemetry['gps']['alt']
                    }
                    drone_state['altitude'] = telemetry['gps']['alt']

                # Extract battery info
                if telemetry.get('battery'):
                    drone_state['battery_percent'] = telemetry['battery']['battery_remaining']
                    drone_state['battery_voltage'] = telemetry['battery']['voltage']

                # Extract GPS info
                if telemetry.get('gps'):
                    drone_state['satellites'] = telemetry['gps']['satellites_visible']
                    drone_state['gps_fix'] = telemetry['gps']['fix_type']

                # Extract speed and heading
                if telemetry.get('vfr_hud'):
                    drone_state['ground_speed'] = telemetry['vfr_hud']['groundspeed']
                    drone_state['heading'] = telemetry['vfr_hud']['heading']
                elif telemetry.get('gps'):
                    drone_state['ground_speed'] = telemetry['gps']['vel']
                    drone_state['heading'] = telemetry['gps']['cog']

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

                update['drones'].append(drone_state)

            # Emit to all connected clients
            socketio.emit('telemetry_update', update)

            # Sleep until next update
            time.sleep(update_interval)

        except Exception as e:
            logger.error(f"Error in telemetry stream: {e}")
            time.sleep(1)


def initialize_mavlink():
    """Initialize MAVLink connections in background"""
    def connect():
        logger.info("Connecting to PX4 instances...")
        mavlink_manager.connect_all()
        logger.info("MAVLink initialization complete")

    init_thread = threading.Thread(target=connect, daemon=True)
    init_thread.start()


if __name__ == '__main__':
    logger.info("=" * 60)
    logger.info("PX4 Command & Control Dashboard Backend")
    logger.info("=" * 60)
    logger.info(f"Configured drones: {len(config.DRONES)}")
    for drone in config.DRONES:
        logger.info(f"  - {drone['name']}: {drone['host']}:{drone['port']}")
    logger.info(f"Update rate: {config.TELEMETRY_UPDATE_HZ} Hz")
    logger.info("=" * 60)

    # Initialize MAVLink connections
    initialize_mavlink()

    # Start Flask-SocketIO server
    logger.info(f"Starting server on {config.HOST}:{config.PORT}")
    socketio.run(
        app,
        host=config.HOST,
        port=config.PORT,
        debug=config.DEBUG,
        allow_unsafe_werkzeug=True
    )
