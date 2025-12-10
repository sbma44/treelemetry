#!/bin/bash
# MQTT Logger Email Debug Script
# Comprehensive email troubleshooting for Docker deployment

set -e

CONTAINER_NAME="${1:-mqtt-logger}"

echo "========================================="
echo "MQTT Logger Email Debug"
echo "Container: $CONTAINER_NAME"
echo "========================================="
echo ""

# Check if container exists
if ! docker ps -a | grep -q "$CONTAINER_NAME"; then
    echo "❌ Error: Container '$CONTAINER_NAME' not found"
    echo ""
    echo "Available containers:"
    docker ps -a --format "{{.Names}}"
    exit 1
fi

# Check if container is running
if ! docker ps | grep -q "$CONTAINER_NAME"; then
    echo "⚠️  Warning: Container '$CONTAINER_NAME' is not running"
    echo ""
fi

echo "1️⃣  Container Status:"
docker ps -a | grep "$CONTAINER_NAME" || echo "Not found"
echo ""

echo "2️⃣  Environment Variables:"
echo "   ALERT_EMAIL_TO:"
docker exec "$CONTAINER_NAME" env | grep ALERT_EMAIL_TO || echo "   Not set"
echo "   SMTP settings (from msmtprc):"
if docker exec "$CONTAINER_NAME" test -f /root/.msmtprc 2>/dev/null; then
    docker exec "$CONTAINER_NAME" grep -E "^(host|port|from|user)" /root/.msmtprc 2>/dev/null || echo "   msmtprc exists but can't read settings"
else
    echo "   ❌ /root/.msmtprc does NOT exist (rebuild with --build-arg SMTP_* flags)"
fi
echo ""

echo "3️⃣  Startup Email Status:"
docker logs "$CONTAINER_NAME" 2>&1 | grep -A2 "Sending startup notification" || echo "   No startup email attempt found in logs"
echo ""

echo "4️⃣  msmtp Log File:"
if docker exec "$CONTAINER_NAME" test -f /app/logs/msmtp.log 2>/dev/null; then
    echo "   Last 15 lines of msmtp.log:"
    docker exec "$CONTAINER_NAME" tail -15 /app/logs/msmtp.log 2>/dev/null || echo "   Can't read log"
else
    echo "   ❌ /app/logs/msmtp.log does NOT exist"
    echo "   Check if /app/logs is mounted as a volume"
fi
echo ""

echo "5️⃣  Host Log Directory (if mounted):"
if [ -d "./logs" ]; then
    echo "   ✅ ./logs directory exists"
    if [ -f "./logs/msmtp.log" ]; then
        echo "   ✅ ./logs/msmtp.log exists"
        echo "   Last 10 lines:"
        tail -10 ./logs/msmtp.log
    else
        echo "   ⚠️  ./logs/msmtp.log does NOT exist yet"
    fi
else
    echo "   ⚠️  ./logs directory not found in current directory"
    echo "   Logs may be mounted elsewhere or not mounted at all"
fi
echo ""

echo "6️⃣  Testing Email Send:"
echo "   Sending test email..."
if docker exec "$CONTAINER_NAME" bash -c 'echo "Debug test from $(date)" | mail -s "MQTT Logger Email Debug Test" "$ALERT_EMAIL_TO"' 2>/dev/null; then
    echo "   ✅ mail command executed (check email and msmtp.log for results)"
else
    echo "   ❌ mail command failed"
fi
echo ""

echo "7️⃣  Recent msmtp Log (after test):"
if docker exec "$CONTAINER_NAME" test -f /app/logs/msmtp.log 2>/dev/null; then
    echo "   Last 5 lines:"
    docker exec "$CONTAINER_NAME" tail -5 /app/logs/msmtp.log 2>/dev/null
else
    echo "   Log file not found"
fi
echo ""

echo "========================================="
echo "Debug Summary"
echo "========================================="
echo ""
echo "What to check:"
echo ""
echo "1. Subject line: 'MQTT Logger Started Successfully'"
echo "   Check spam/junk folder!"
echo ""
echo "2. msmtp.log should show:"
echo "   - Connection to SMTP server"
echo "   - Authentication success"
echo "   - Message accepted"
echo ""
echo "3. Common issues:"
echo "   • msmtprc missing → Rebuild with SMTP build args"
echo "   • Authentication failed → Check SMTP_PASSWORD"
echo "   • Connection timeout → Check SMTP_SERVER and SMTP_PORT"
echo "   • TLS errors → Check ca-certificates in container"
echo ""
echo "To view logs continuously:"
echo "   tail -f ./logs/msmtp.log"
echo ""
echo "To test email manually in container:"
echo "   docker exec -it $CONTAINER_NAME bash"
echo "   echo 'Test' | mail -s 'Manual Test' your@email.com"
echo "   cat /app/logs/msmtp.log"
echo ""

