# Use official uv image with Python 3.12
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# Build arguments for SMTP configuration
ARG SMTP_SERVER=""
ARG SMTP_PORT="587"
ARG SMTP_FROM=""
ARG SMTP_TO=""
ARG SMTP_PASSWORD=""

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    msmtp \
    msmtp-mta \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/msmtp /usr/bin/mail 2>/dev/null || true \
    && ln -sf /usr/bin/msmtp /usr/sbin/sendmail 2>/dev/null || true

# Configure msmtp if SMTP settings are provided
RUN if [ -n "$SMTP_SERVER" ]; then \
    mkdir -p /root && \
    echo "defaults" > /root/.msmtprc && \
    echo "auth           on" >> /root/.msmtprc && \
    echo "tls            on" >> /root/.msmtprc && \
    echo "tls_trust_file /etc/ssl/certs/ca-certificates.crt" >> /root/.msmtprc && \
    echo "logfile        /app/logs/msmtp.log" >> /root/.msmtprc && \
    echo "" >> /root/.msmtprc && \
    echo "account        mqtt_alerts" >> /root/.msmtprc && \
    echo "host           $SMTP_SERVER" >> /root/.msmtprc && \
    echo "port           $SMTP_PORT" >> /root/.msmtprc && \
    echo "from           $SMTP_FROM" >> /root/.msmtprc && \
    echo "user           $SMTP_TO" >> /root/.msmtprc && \
    echo "password       $SMTP_PASSWORD" >> /root/.msmtprc && \
    echo "" >> /root/.msmtprc && \
    echo "account default : mqtt_alerts" >> /root/.msmtprc && \
    chmod 600 /root/.msmtprc; \
    fi

# Copy project files
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY main.py ./
COPY docker-entrypoint.sh ./

# Install dependencies using uv
RUN uv sync --frozen --no-dev

# Create directories
RUN mkdir -p /app/data /app/config /app/logs

# Make entrypoint executable
RUN chmod +x docker-entrypoint.sh

# Environment variables with defaults
ENV MQTT_BROKER="localhost" \
    MQTT_PORT="1883" \
    MQTT_USERNAME="" \
    MQTT_PASSWORD="" \
    MQTT_CLIENT_ID="" \
    MQTT_KEEPALIVE="60" \
    MQTT_QOS="1" \
    DB_PATH="/app/data/mqtt_logs.db" \
    DB_BATCH_SIZE="5000" \
    DB_FLUSH_INTERVAL="300" \
    TOPICS="test/#:test_messages:Test messages" \
    LOG_LEVEL="INFO" \
    LOG_FILE="" \
    ALERT_EMAIL_TO="" \
    ALERT_DB_SIZE_MB="" \
    ALERT_FREE_SPACE_MB="" \
    ALERT_COOLDOWN_HOURS="24" \
    TZ="UTC"

# Run entrypoint script
ENTRYPOINT ["/app/docker-entrypoint.sh"]

