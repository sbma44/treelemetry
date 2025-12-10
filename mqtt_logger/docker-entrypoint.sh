#!/bin/bash
set -e

# Generate config file from environment variables
CONFIG_FILE="/app/config/mqtt_logger.toml"

echo "Generating configuration from environment variables..."

cat > "$CONFIG_FILE" <<EOF
# Auto-generated from environment variables
# Generated at: $(date)

[mqtt]
broker = "${MQTT_BROKER}"
port = ${MQTT_PORT}
username = "${MQTT_USERNAME}"
password = "${MQTT_PASSWORD}"
client_id = "${MQTT_CLIENT_ID}"
keepalive = ${MQTT_KEEPALIVE}
qos = ${MQTT_QOS}

[database]
path = "${DB_PATH}"
batch_size = ${DB_BATCH_SIZE}
flush_interval = ${DB_FLUSH_INTERVAL}

EOF

# Parse and add topics
# Format: "pattern1:table1:description1;pattern2:table2:description2"
IFS=';' read -ra TOPIC_ARRAY <<< "$TOPICS"
for topic_spec in "${TOPIC_ARRAY[@]}"; do
    IFS=':' read -r pattern table description <<< "$topic_spec"

    # Trim whitespace
    pattern=$(echo "$pattern" | xargs)
    table=$(echo "$table" | xargs)
    description=$(echo "$description" | xargs)

    if [ -n "$pattern" ] && [ -n "$table" ]; then
        cat >> "$CONFIG_FILE" <<EOF
[[topics]]
pattern = "${pattern}"
table_name = "${table}"
EOF
        if [ -n "$description" ]; then
            echo "description = \"${description}\"" >> "$CONFIG_FILE"
        fi
        echo "" >> "$CONFIG_FILE"
    fi
done

# Add logging configuration
cat >> "$CONFIG_FILE" <<EOF
[logging]
level = "${LOG_LEVEL}"
format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
EOF

if [ -n "$LOG_FILE" ]; then
    echo "file = \"${LOG_FILE}\"" >> "$CONFIG_FILE"
fi

echo "" >> "$CONFIG_FILE"

# Add alerting configuration
cat >> "$CONFIG_FILE" <<EOF
[alerting]
EOF

if [ -n "$ALERT_EMAIL_TO" ]; then
    echo "email_to = \"${ALERT_EMAIL_TO}\"" >> "$CONFIG_FILE"
else
    echo "email_to = \"\"" >> "$CONFIG_FILE"
fi

if [ -n "$ALERT_DB_SIZE_MB" ]; then
    echo "db_size_threshold_mb = ${ALERT_DB_SIZE_MB}" >> "$CONFIG_FILE"
fi

if [ -n "$ALERT_FREE_SPACE_MB" ]; then
    echo "free_space_threshold_mb = ${ALERT_FREE_SPACE_MB}" >> "$CONFIG_FILE"
fi

echo "alert_cooldown_hours = ${ALERT_COOLDOWN_HOURS}" >> "$CONFIG_FILE"

echo "Configuration generated successfully:"
echo "----------------------------------------"
cat "$CONFIG_FILE"
echo "----------------------------------------"

# Startup notification is now sent by Python code after config is loaded
# This ensures the email shows actual values after env var overrides

# Run the application
exec uv run python main.py "$CONFIG_FILE"

