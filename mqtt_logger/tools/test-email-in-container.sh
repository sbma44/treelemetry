#!/bin/bash
# Test email from inside the container
# Usage: ./test-email-in-container.sh [container-name] [email-address]

CONTAINER="${1:-mqtt-logger}"
EMAIL="${2:-$ALERT_EMAIL_TO}"

if [ -z "$EMAIL" ]; then
    echo "Error: Email address required"
    echo "Usage: $0 [container-name] [email-address]"
    exit 1
fi

echo "Testing email in container: $CONTAINER"
echo "Sending to: $EMAIL"
echo ""

docker exec "$CONTAINER" bash -c "cat <<EOF | /usr/bin/msmtp -t
To: $EMAIL
Subject: MQTT Logger Test Email - $(date)

This is a test email sent at: $(date)

Container: \$(hostname)

If you receive this, email is working!
EOF"

EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ Email sent successfully!"
    echo ""
    echo "Check your inbox for: 'MQTT Logger Test Email'"
    echo "Also check spam/junk folder"
else
    echo "❌ Failed to send email (exit code: $EXIT_CODE)"
    echo ""
    echo "Check msmtp log:"
    echo "  docker exec $CONTAINER cat /app/logs/msmtp.log"
fi

echo ""
echo "View msmtp log:"
docker exec "$CONTAINER" cat /app/logs/msmtp.log 2>/dev/null || echo "No log file yet"

