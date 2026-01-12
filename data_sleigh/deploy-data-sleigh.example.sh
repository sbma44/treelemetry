#!/bin/bash
# Deploy Data Sleigh to a remote host
#
# This script:
# 1. Stops the existing mqtt_logger and uploader containers
# 2. Copies the data_sleigh directory to the remote host
# 3. Builds the Docker image with SMTP configuration
# 4. Runs the container using run-docker-data-sleigh.sh
#
# SETUP:
#   1. Copy this file: cp deploy-data-sleigh.example.sh deploy-data-sleigh.sh
#   2. Edit deploy-data-sleigh.sh with your actual values
#   3. Run: ./deploy-data-sleigh.sh
#
# Usage:
#   ./deploy-data-sleigh.sh [REMOTE_DIR]
#
# Arguments:
#   REMOTE_DIR - Target directory on remote host (default: /home/username/docker/data_sleigh)

set -eu -o pipefail

# Configuration - EDIT THESE VALUES
REMOTE_HOST="${REMOTE_HOST:-YOUR_REMOTE_HOST_IP}"
REMOTE_USER="${REMOTE_USER:-YOUR_USERNAME}"
REMOTE_DIR="${1:-/home/YOUR_USERNAME/docker/data_sleigh}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Container IDs to stop (optional - set to your existing container IDs)
UPLOADER_CONTAINER="${UPLOADER_CONTAINER:-}"
MQTT_LOGGER_CONTAINER="${MQTT_LOGGER_CONTAINER:-}"

# SMTP Configuration for build args
SMTP_SERVER="${SMTP_SERVER:-smtp.gmail.com}"
SMTP_PORT="${SMTP_PORT:-587}"
SMTP_FROM="${SMTP_FROM:-your-email@example.com}"
SMTP_TO="${SMTP_TO:-your-email@example.com}"
SMTP_PASSWORD="${SMTP_PASSWORD:-}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

ssh_cmd() {
    ssh "${REMOTE_USER}@${REMOTE_HOST}" "bash -l -c '$1'"
}

echo "========================================"
echo "  Data Sleigh Deployment Script"
echo "========================================"
echo ""
echo "Remote host: ${REMOTE_USER}@${REMOTE_HOST}"
echo "Remote directory: ${REMOTE_DIR}"
echo "Source directory: ${SCRIPT_DIR}"
echo ""

# Check if SMTP_PASSWORD is set
if [ -z "$SMTP_PASSWORD" ]; then
    log_warn "SMTP_PASSWORD not set. Email alerts will not work."
    log_warn "Set SMTP_PASSWORD environment variable or edit docker_env.sh on the remote host."
    echo ""
fi

# Step 1: Stop existing containers (if container IDs are set)
log_info "Step 1: Stopping existing containers..."
echo ""

if [ -n "$UPLOADER_CONTAINER" ]; then
    log_info "Stopping uploader container (${UPLOADER_CONTAINER})..."
    if ssh_cmd "docker stop ${UPLOADER_CONTAINER} 2>/dev/null && docker rm ${UPLOADER_CONTAINER} 2>/dev/null"; then
        log_info "Uploader container stopped and removed."
    else
        log_warn "Uploader container not running or already removed."
    fi
fi

if [ -n "$MQTT_LOGGER_CONTAINER" ]; then
    log_info "Stopping mqtt_logger container (${MQTT_LOGGER_CONTAINER})..."
    if ssh_cmd "docker stop ${MQTT_LOGGER_CONTAINER} 2>/dev/null && docker rm ${MQTT_LOGGER_CONTAINER} 2>/dev/null"; then
        log_info "MQTT logger container stopped and removed."
    else
        log_warn "MQTT logger container not running or already removed."
    fi
fi

echo ""

# Step 2: Create remote directory and copy files
log_info "Step 2: Copying data_sleigh to remote host..."
echo ""

# Create remote directory
ssh_cmd "mkdir -p ${REMOTE_DIR}"

# Create data and logs directories
ssh_cmd "mkdir -p ${REMOTE_DIR}/data ${REMOTE_DIR}/logs"

# Copy files using rsync (faster and handles incremental updates)
# Exclude __pycache__, .git, tests, and other dev files
rsync -avz --progress \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude '.git' \
    --exclude '.pytest_cache' \
    --exclude 'tests' \
    --exclude '*.egg-info' \
    --exclude '.venv' \
    "${SCRIPT_DIR}/" \
    "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_DIR}/"

log_info "Files copied successfully."
echo ""

# Step 3: Build the Docker image
log_info "Step 3: Building Docker image with SMTP configuration..."
echo ""

BUILD_CMD="cd ${REMOTE_DIR} && docker build"

# Add SMTP build args if password is set
if [ -n "$SMTP_PASSWORD" ]; then
    BUILD_CMD="${BUILD_CMD} --build-arg SMTP_SERVER=${SMTP_SERVER}"
    BUILD_CMD="${BUILD_CMD} --build-arg SMTP_PORT=${SMTP_PORT}"
    BUILD_CMD="${BUILD_CMD} --build-arg SMTP_FROM=${SMTP_FROM}"
    BUILD_CMD="${BUILD_CMD} --build-arg SMTP_TO=${SMTP_TO}"
    BUILD_CMD="${BUILD_CMD} --build-arg SMTP_PASSWORD='${SMTP_PASSWORD}'"
fi

BUILD_CMD="${BUILD_CMD} -t data-sleigh:latest ."

ssh_cmd "${BUILD_CMD}"

log_info "Docker image built successfully."
echo ""

# Step 4: Run the container
log_info "Step 4: Starting data-sleigh container..."
echo ""

ssh_cmd "cd ${REMOTE_DIR} && chmod +x run-docker-data-sleigh.sh && ./run-docker-data-sleigh.sh"

echo ""
log_info "Deployment complete!"
echo ""
echo "========================================"
echo "  Deployment Summary"
echo "========================================"
echo ""
echo "New container: data-sleigh"
echo ""
echo "Useful commands (run on remote host):"
echo "  docker logs -f data-sleigh      # View logs"
echo "  docker ps | grep data-sleigh    # Check status"
echo "  docker stop data-sleigh         # Stop container"
echo "  docker start data-sleigh        # Start container"
echo ""
echo "The data_sleigh container now handles both MQTT logging and S3 uploads."
echo ""

