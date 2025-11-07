# Configuration for PX4 Dashboard Backend - FIXED VERSION

# ============================================================================
# CONNECTION MODE - Choose your setup:
# ============================================================================
#
# MODE 1: Local PX4 SITL (everything on same machine)
#   - Use "127.0.0.1" for host
#   - Good for: development, testing, demo
#
# MODE 2: Remote PX4 with SSH Tunnel (RECOMMENDED for your Oracle setup)
#   - Use "127.0.0.1" for host
#   - Run: ssh -L 14580:localhost:14580 -L 14581:localhost:14581 -L 14582:localhost:14582 ubuntu@129.153.124.182 -N
#   - Good for: secure remote access
#
# MODE 3: Direct Remote Connection (requires firewall rules)
#   - Use "129.XXX.124.XXX" for host
#   - Requires: sudo ufw allow 14580-14582/udp on remote server
#   - Warning: Exposes PX4 to internet - not recommended for production
#
# ============================================================================

# Current Configuration: Local/Tunneled
DRONES = [
    {
        "id": 1,
        "name": "Drone Alpha",
        "host": "127.0.0.1",  # Change to "129.153.124.182" for direct remote
        "port": 14540,
        "system_id": 1,  # FIX: PX4 system ID (matches instance number)
        "color": "#3B82F6"  # Blue
    },
    {
        "id": 2,
        "name": "Drone Bravo",
        "host": "127.0.0.1",  # Change to "129.153.124.182" for direct remote
        "port": 14541,
        "system_id": 2,  # FIX: PX4 system ID (matches instance number)
        "color": "#10B981"  # Green
    },
    {
        "id": 3,
        "name": "Drone Charlie",
        "host": "127.0.0.1",  # Change to "129.153.124.182" for direct remote
        "port": 14542,
        "system_id": 3,  # FIX: PX4 system ID (matches instance number)
        "color": "#F59E0B"  # Amber
    }
]

# Update Rates
TELEMETRY_UPDATE_HZ = 5  # Send updates to frontend at 5 Hz
METRICS_WINDOW_SIZE = 100  # Keep last 100 data points for charts

# Network Metrics
LATENCY_THRESHOLD_MS = 100  # Warn if latency exceeds this
JITTER_THRESHOLD_MS = 20     # Warn if jitter exceeds this

# Flask Settings
HOST = '0.0.0.0'
PORT = 5000
DEBUG = False  # IMPORTANT: Must be False to prevent auto-reloader from creating duplicate UDP listeners

# CORS Settings
# Add your frontend URLs here when deploying to separate platforms
CORS_ALLOWED_ORIGINS = [
    "https://axon-c2-poc.vercel.app",
    "http://35.151.134.67:3000",              # Local development (alt)
    # Production examples - uncomment and update with your actual domains:
    # "https://your-app.vercel.app",      # Vercel
    # "https://your-app.netlify.app",     # Netlify
    # "https://yourdomain.com",           # Custom domain
]

# Allow all origins in development (NOT for production!)
CORS_ALLOW_ALL = False  # Set to True only for development testing
