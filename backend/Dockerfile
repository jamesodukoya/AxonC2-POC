# AxonPOC Backend Dockerfile - Production Ready with Supervisord
# Python 3.11 slim base image for smaller size

FROM python:3.11-slim

# Metadata
LABEL maintainer="jay@axonpoc.com"
LABEL description="PX4 Command & Control Dashboard Backend with Supervisord"
LABEL version="2.0"

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Set working directory
WORKDIR /app

# Install system dependencies
# - gcc: Required for building Python packages with C extensions
# - supervisor: Process control system for auto-restart
# - procps: Provides ps, pgrep, pkill commands
# - Clean up apt cache to reduce image size
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    supervisor \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for better layer caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user for security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# Create logs directory with proper permissions
RUN mkdir -p /app/logs && \
    chown -R appuser:appuser /app/logs

# Create supervisor log directory
RUN mkdir -p /var/log/supervisor && \
    chown -R appuser:appuser /var/log/supervisor

# Copy supervisord configuration
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Expose port (documentation only, actual binding happens at runtime)
EXPOSE 5000

# Health check - checks if backend API is responding
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/').read()" || exit 1

# Run supervisord (manages both app.py and commander.py)
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]