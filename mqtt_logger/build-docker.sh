#!/bin/bash
# Build MQTT Logger Docker image with email alerts support

set -e

# Default values (can be overridden with environment variables)
SMTP_SERVER=${SMTP_SERVER:-""}
SMTP_PORT=${SMTP_PORT:-"587"}
SMTP_FROM=${SMTP_FROM:-""}
SMTP_TO=${SMTP_TO:-""}
SMTP_PASSWORD=${SMTP_PASSWORD:-""}

echo "Building MQTT Logger Docker image..."
echo "=================================="

if [ -n "$SMTP_SERVER" ]; then
    echo "Email alerts: ENABLED"
    echo "  SMTP Server: $SMTP_SERVER"
    echo "  SMTP Port: $SMTP_PORT"
    echo "  From: $SMTP_FROM"
    echo "  To: $SMTP_TO"
    echo ""

    docker build \
        --build-arg SMTP_SERVER="$SMTP_SERVER" \
        --build-arg SMTP_PORT="$SMTP_PORT" \
        --build-arg SMTP_FROM="$SMTP_FROM" \
        --build-arg SMTP_TO="$SMTP_TO" \
        --build-arg SMTP_PASSWORD="$SMTP_PASSWORD" \
        -t mqtt-logger:latest \
        .
else
    echo "Email alerts: DISABLED"
    echo "(Set SMTP_* environment variables to enable)"
    echo ""

    docker build -t mqtt-logger:latest .
fi

echo ""
echo "=================================="
echo "✅ Build complete! Image: mqtt-logger:latest"
echo ""
echo "Quick start:"
echo "  docker run -d --name mqtt-logger \\"
echo "    -v \$(pwd)/data:/app/data \\"
echo "    -v \$(pwd)/logs:/app/logs \\"
echo "    -e MQTT_BROKER=your-broker \\"
echo "    -e TOPICS=\"topic/#:table:Description\" \\"
if [ -n "$SMTP_SERVER" ]; then
    echo "    -e ALERT_EMAIL_TO=you@example.com \\"
fi
echo "    mqtt-logger:latest"
echo ""
echo "📧 Startup email notification: $([ -n "$SMTP_SERVER" ] && echo "ENABLED" || echo "Disabled (no SMTP configured)")"
if [ -n "$SMTP_SERVER" ]; then
    echo ""
    echo "To debug email issues:"
    echo "  ./debug-email.sh mqtt-logger"
    echo "  tail -f logs/msmtp.log"
fi
echo ""
echo "📖 Full documentation: DOCKER.md"
echo ""

