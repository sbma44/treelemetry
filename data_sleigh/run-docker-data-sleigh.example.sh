#!/bin/bash
# Run Data Sleigh in Docker
# This script replaces both mqtt_logger and treelemetry-uploader
#
# SETUP:
#   1. Copy this file: cp run-docker-data-sleigh.example.sh run-docker-data-sleigh.sh
#   2. Edit run-docker-data-sleigh.sh with your actual values
#   3. Run: ./run-docker-data-sleigh.sh

set -eu -o pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Source SMTP configuration (optional - create docker_env.sh if needed)
# source "${SCRIPT_DIR}/../docker_env.sh"

# Configuration
CONTAINER_NAME="data-sleigh"
IMAGE_NAME="data-sleigh:latest"
DATA_DIR="${DATA_DIR:-${SCRIPT_DIR}/data}"
LOGS_DIR="${LOGS_DIR:-${SCRIPT_DIR}/logs}"

# MQTT Configuration
MQTT_BROKER="${MQTT_BROKER:-YOUR_MQTT_BROKER_IP}"
MQTT_PORT="${MQTT_PORT:-1883}"
MQTT_USERNAME="${MQTT_USERNAME:-}"
MQTT_PASSWORD="${MQTT_PASSWORD:-}"
TOPICS="${TOPICS:-xmas/tree/water/raw:water_level:Tree water level}"

# Database Configuration
DB_BATCH_SIZE="${DB_BATCH_SIZE:-100}"
DB_FLUSH_INTERVAL="${DB_FLUSH_INTERVAL:-30}"

# YoLink Configuration
YOLINK_UAID="${YOLINK_UAID:-YOUR_YOLINK_UAID}"
YOLINK_SECRET_KEY="${YOLINK_SECRET_KEY:-YOUR_YOLINK_SECRET_KEY}"
YOLINK_AIR_SENSOR_DEVICEID="${YOLINK_AIR_SENSOR_DEVICEID:-YOUR_AIR_SENSOR_DEVICE_ID}"
YOLINK_WATER_SENSOR_DEVICEID="${YOLINK_WATER_SENSOR_DEVICEID:-YOUR_WATER_SENSOR_DEVICE_ID}"

# Season Configuration
SEASON_START="${SEASON_START:-2025-12-01}"
SEASON_END="${SEASON_END:-2026-01-15}"

# S3/AWS Configuration
S3_BUCKET="${S3_BUCKET:-YOUR_S3_BUCKET_NAME}"
S3_JSON_KEY="${S3_JSON_KEY:-water-level.json}"
S3_BACKUP_PREFIX="${S3_BACKUP_PREFIX:-backups/}"
AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-YOUR_AWS_ACCESS_KEY_ID}"
AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-YOUR_AWS_SECRET_ACCESS_KEY}"

# Upload Configuration
UPLOAD_INTERVAL_SECONDS="${UPLOAD_INTERVAL_SECONDS:-30}"
MINUTES_OF_DATA="${MINUTES_OF_DATA:-10}"
REPLAY_DELAY_SECONDS="${REPLAY_DELAY_SECONDS:-300}"

# Backup Configuration
BACKUP_DAY_OF_MONTH="${BACKUP_DAY_OF_MONTH:-1}"
BACKUP_HOUR="${BACKUP_HOUR:-3}"

# Alert Configuration
ALERT_EMAIL_TO="${ALERT_EMAIL_TO:-your-email@example.com}"
ALERT_DB_SIZE_MB="${ALERT_DB_SIZE_MB:-}"
ALERT_FREE_SPACE_MB="${ALERT_FREE_SPACE_MB:-}"

# Timezone
TZ="${TZ:-EST}"

# Create directories if they don't exist
mkdir -p "$DATA_DIR"
mkdir -p "$LOGS_DIR"

echo "Starting Data Sleigh..."
echo "======================="
echo "MQTT Broker: $MQTT_BROKER"
echo "Topics: $TOPICS"
echo "Season: $SEASON_START to $SEASON_END"
echo "S3 Bucket: $S3_BUCKET"
echo "Data directory: $DATA_DIR"
echo "Logs directory: $LOGS_DIR"
echo "Email alerts: ${ALERT_EMAIL_TO:-disabled}"
echo ""

# Stop existing container if running
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "Stopping existing container..."
    docker stop "$CONTAINER_NAME" 2>/dev/null || true
    docker rm "$CONTAINER_NAME" 2>/dev/null || true
fi

# Run the container
docker run -d \
  --name "$CONTAINER_NAME" \
  --restart unless-stopped \
  -v "$DATA_DIR":/app/data \
  -v "$LOGS_DIR":/app/logs \
  -e TZ="$TZ" \
  -e MQTT_BROKER="$MQTT_BROKER" \
  -e MQTT_PORT="$MQTT_PORT" \
  -e MQTT_USERNAME="$MQTT_USERNAME" \
  -e MQTT_PASSWORD="$MQTT_PASSWORD" \
  -e TOPICS="$TOPICS" \
  -e DB_BATCH_SIZE="$DB_BATCH_SIZE" \
  -e DB_FLUSH_INTERVAL="$DB_FLUSH_INTERVAL" \
  -e YOLINK_UAID="$YOLINK_UAID" \
  -e YOLINK_SECRET_KEY="$YOLINK_SECRET_KEY" \
  -e YOLINK_AIR_SENSOR_DEVICEID="$YOLINK_AIR_SENSOR_DEVICEID" \
  -e YOLINK_WATER_SENSOR_DEVICEID="$YOLINK_WATER_SENSOR_DEVICEID" \
  -e SEASON_START="$SEASON_START" \
  -e SEASON_END="$SEASON_END" \
  -e S3_BUCKET="$S3_BUCKET" \
  -e S3_JSON_KEY="$S3_JSON_KEY" \
  -e S3_BACKUP_PREFIX="$S3_BACKUP_PREFIX" \
  -e AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID" \
  -e AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY" \
  -e UPLOAD_INTERVAL_SECONDS="$UPLOAD_INTERVAL_SECONDS" \
  -e MINUTES_OF_DATA="$MINUTES_OF_DATA" \
  -e REPLAY_DELAY_SECONDS="$REPLAY_DELAY_SECONDS" \
  -e BACKUP_DAY_OF_MONTH="$BACKUP_DAY_OF_MONTH" \
  -e BACKUP_HOUR="$BACKUP_HOUR" \
  -e ALERT_EMAIL_TO="$ALERT_EMAIL_TO" \
  -e ALERT_DB_SIZE_MB="$ALERT_DB_SIZE_MB" \
  -e ALERT_FREE_SPACE_MB="$ALERT_FREE_SPACE_MB" \
  "$IMAGE_NAME"

echo ""
echo "======================="
echo "Container started successfully!"
echo ""
echo "View logs:"
echo "  docker logs -f $CONTAINER_NAME"
echo ""
echo "Check status:"
echo "  docker ps | grep $CONTAINER_NAME"
echo ""
echo "Stop with:"
echo "  docker stop $CONTAINER_NAME"


