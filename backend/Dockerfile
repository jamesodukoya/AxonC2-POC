# AxonPOC Backend Dockerfile - Production Ready with Supervisord
# Python 3.11 slim base image for smaller size

FROM python:3.11-slim

# Metadata
LABEL maintainer="odukoyajames@gmail.com"
LABEL description="PX4 Command & Control Dashboard Backend with Supervisord"
LABEL version="2.0"

# Install sudo first
RUN apt-get update && apt-get install -y --no-install-recommends \
    sudo \
    && rm -rf /var/lib/apt/lists/*

# Arguments for user creation
ARG USERNAME=user
ARG USER_UID=1000
ARG USER_GID=$USER_UID

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Create non-root user with sudo privileges
RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME -s /bin/bash \
    && echo "$USERNAME:$USERNAME" | chpasswd \
    && echo "$USERNAME ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME

# Create workspace directory
RUN mkdir -p /home/$USERNAME/app && \
    chown -R $USERNAME:$USERNAME /home/$USERNAME


# Install system dependencies
# - gcc: Required for building Python packages with C extensions
# - supervisor: Process control system for auto-restart
# - procps: Provides ps, pgrep, pkill commands
# - Clean up apt cache to reduce image size
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    procps \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
# Switch to user
USER $USERNAME
WORKDIR /home/$USERNAME

# Copy requirements first (for better layer caching)
COPY requirements.txt /home/$USERNAME

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . /home/$USERNAME

# Copy supervisor configuration
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Copy startup delay script
COPY start_commander.sh /home/$USERNAME/start_commander.sh
RUN chmod +x /home/$USERNAME/start_commander.sh && \
    chown $USERNAME:$USERNAME /home/$USERNAME/start_commander.sh



# Expose port (documentation only, actual binding happens at runtime)
EXPOSE 5000

# Default command
# Start supervisord
CMD ["/usr/bin/supervisord", "-n", "-c", "/etc/supervisor/conf.d/supervisord.conf"]