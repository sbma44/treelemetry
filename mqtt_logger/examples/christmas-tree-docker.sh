#!/bin/bash
# Christmas Tree Water Level Monitor - Docker Deployment
# 🎄 Because over-engineering holiday decorations is a tradition!

set -e

echo "🎄 Christmas Tree Water Level Monitor"
echo "====================================="
echo ""

# Configuration
MQTT_BROKER="${MQTT_BROKER:-192.168.1.100}"
ALERT_EMAIL="${ALERT_EMAIL:-}"
DATA_DIR="${DATA_DIR:-$(pwd)/tree-data}"
LOGS_DIR="${LOGS_DIR:-$(pwd)/tree-logs}"

# Create directories
mkdir -p "$DATA_DIR"
mkdir -p "$LOGS_DIR"

echo "Configuration:"
echo "  MQTT Broker: $MQTT_BROKER"
echo "  Data Directory: $DATA_DIR"
echo "  Logs Directory: $LOGS_DIR"
echo "  Email Alerts: ${ALERT_EMAIL:-disabled}"
echo ""

# Stop existing container if running
if docker ps -a | grep -q christmas-tree; then
    echo "Stopping existing Christmas tree monitor..."
    docker stop christmas-tree 2>/dev/null || true
    docker rm christmas-tree 2>/dev/null || true
fi

# Run the container
echo "Starting Christmas tree water monitor..."
docker run -d \
  --name christmas-tree \
  --restart unless-stopped \
  -v "$DATA_DIR":/app/data \
  -v "$LOGS_DIR":/app/logs \
  -e TZ=America/New_York \
  -e MQTT_BROKER="$MQTT_BROKER" \
  -e TOPICS="christmas/tree/water/#:water_level:Tree water level;christmas/tree/status/#:tree_status:Tree status" \
  -e DB_PATH=/app/data/christmas_tree.db \
  -e DB_BATCH_SIZE=5000 \
  -e DB_FLUSH_INTERVAL=300 \
  -e LOG_LEVEL=INFO \
  ${ALERT_EMAIL:+-e ALERT_EMAIL_TO=$ALERT_EMAIL} \
  ${ALERT_EMAIL:+-e ALERT_DB_SIZE_MB=100} \
  ${ALERT_EMAIL:+-e ALERT_FREE_SPACE_MB=500} \
  mqtt-logger:latest

echo ""
echo "🎄 Christmas tree monitor started!"
echo ""
echo "Check application logs:"
echo "  docker logs -f christmas-tree"
echo ""
echo "Check email/SMTP logs:"
echo "  tail -f $LOGS_DIR/msmtp.log"
echo ""
echo "Query water levels:"
echo "  duckdb $DATA_DIR/christmas_tree.db \"SELECT * FROM water_level ORDER BY timestamp DESC LIMIT 10\""
echo ""
echo "Stop with:"
echo "  docker stop christmas-tree"

