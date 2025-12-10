#!/bin/bash
# Run MQTT Logger in Docker with example configuration

set -e

# Configuration - EDIT THESE VALUES
MQTT_BROKER="${MQTT_BROKER:-192.168.1.2}"
MQTT_USERNAME="${MQTT_USERNAME:-}"
MQTT_PASSWORD="${MQTT_PASSWORD:-}"
TOPICS="${TOPICS:-xmas/tree/water/raw:water_level:Tree water level}"
ALERT_EMAIL="${ALERT_EMAIL:-your-email@gmail.com}"
DATA_DIR="${DATA_DIR:-$(pwd)/data}"
LOGS_DIR="${LOGS_DIR:-$(pwd)/logs}"

# Create directories if they don't exist
mkdir -p "$DATA_DIR"
mkdir -p "$LOGS_DIR"

echo "Starting MQTT Logger..."
echo "====================="
echo "MQTT Broker: $MQTT_BROKER"
echo "Topics: $TOPICS"
echo "Data directory: $DATA_DIR"
echo "Logs directory: $LOGS_DIR"
echo "Email alerts: ${ALERT_EMAIL:-disabled}"
echo ""

# Build docker run command
CMD="docker run -d \
  --name xmas-mqtt-logger \
  --restart unless-stopped \
  -v $DATA_DIR:/app/data \
  -v $LOGS_DIR:/app/logs \
  -e TZ=$(date +%Z) \
  -e MQTT_BROKER=$MQTT_BROKER"

# Add optional parameters
[ -n "$MQTT_USERNAME" ] && CMD="$CMD -e MQTT_USERNAME=$MQTT_USERNAME"
[ -n "$MQTT_PASSWORD" ] && CMD="$CMD -e MQTT_PASSWORD=$MQTT_PASSWORD"
[ -n "$TOPICS" ] && CMD="$CMD -e TOPICS=\"$TOPICS\""
[ -n "$ALERT_EMAIL" ] && CMD="$CMD -e ALERT_EMAIL_TO=$ALERT_EMAIL"

# Add image name
CMD="$CMD mqtt-logger:latest"

# Stop existing container if running
if docker ps -a | grep -q mqtt-logger; then
    echo "Stopping existing container..."
    docker stop mqtt-logger 2>/dev/null || true
    docker rm mqtt-logger 2>/dev/null || true
fi

# Run the container
echo "Starting container..."
eval $CMD

echo ""
echo "====================="
echo "Container started successfully!"
echo ""
echo "View application logs:"
echo "  docker logs -f mqtt-logger"
echo ""
echo "View SMTP/email logs:"
echo "  tail -f $LOGS_DIR/msmtp.log"
echo ""
echo "Stop with:"
echo "  docker stop mqtt-logger"

