# Docker Deployment Guide

Run MQTT Logger in a Docker container with full configuration via environment variables.

## Quick Start

### 1. Build the Image

**Without email alerts:**
```bash
docker build -t mqtt-logger .
```

**With email alerts (recommended):**
```bash
docker build \
  --build-arg SMTP_SERVER=smtp.gmail.com \
  --build-arg SMTP_PORT=587 \
  --build-arg SMTP_FROM=your-email@gmail.com \
  --build-arg SMTP_TO=your-email@gmail.com \
  --build-arg SMTP_PASSWORD=your-app-password \
  -t mqtt-logger .
```

**Note:** The container will send a startup success email when `ALERT_EMAIL_TO` is configured, confirming that MQTT Logger started successfully with your configuration details.

### 2. Run the Container

**Basic usage:**
```bash
docker run -d \
  --name mqtt-logger \
  --restart unless-stopped \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  -e MQTT_BROKER=mqtt.example.com \
  -e TOPICS="sensors/#:sensors:Sensor data" \
  mqtt-logger
```

**Full example with all options:**
```bash
docker run -d \
  --name mqtt-logger \
  --restart unless-stopped \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  -e TZ=America/New_York \
  -e MQTT_BROKER=mqtt.example.com \
  -e MQTT_PORT=1883 \
  -e MQTT_USERNAME=myuser \
  -e MQTT_PASSWORD=mypass \
  -e MQTT_QOS=1 \
  -e DB_PATH=/app/data/mqtt_logs.db \
  -e DB_BATCH_SIZE=5000 \
  -e DB_FLUSH_INTERVAL=300 \
  -e TOPICS="sensors/temp/#:temperature:Temperature sensors;sensors/humidity/#:humidity:Humidity sensors" \
  -e LOG_LEVEL=INFO \
  -e LOG_FILE=/app/logs/mqtt_logger.log \
  -e ALERT_EMAIL_TO=admin@example.com \
  -e ALERT_DB_SIZE_MB=10000 \
  -e ALERT_FREE_SPACE_MB=2000 \
  mqtt-logger
```

**Note:** Always mount both `/app/data` (database) and `/app/logs` (logs including msmtp.log for email debugging).

## Environment Variables

**Important:** Environment variables **override** TOML config values at runtime. This means you can:
1. Use a base TOML config file
2. Override specific values with `-e` flags when running the container
3. No need to rebuild or regenerate config files

### MQTT Configuration

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `MQTT_BROKER` | MQTT broker hostname/IP | `localhost` | `mqtt.example.com` |
| `MQTT_PORT` | MQTT broker port | `1883` | `1883` or `8883` |
| `MQTT_USERNAME` | Username for authentication | `""` (none) | `myuser` |
| `MQTT_PASSWORD` | Password for authentication | `""` (none) | `mypass` |
| `MQTT_CLIENT_ID` | Client ID | `""` (auto) | `mqtt-logger-1` |
| `MQTT_KEEPALIVE` | Keepalive interval (seconds) | `60` | `60` |
| `MQTT_QOS` | Quality of Service (0, 1, or 2) | `1` | `1` |

### Database Configuration

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `DB_PATH` | Database file path | `/app/data/mqtt_logs.db` | `/app/data/tree.db` |
| `DB_BATCH_SIZE` | Messages to batch before write | `5000` | `1000` or `10000` |
| `DB_FLUSH_INTERVAL` | Seconds between writes | `300` | `60` or `600` |

### Topics Configuration

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `TOPICS` | Topic specifications (see below) | `test/#:test_messages:Test messages` | Multiple topics with semicolons |

**Topics Format:**
```
pattern:table_name:description;pattern2:table_name2:description2
```

**Examples:**
- Single topic: `"sensors/#:all_sensors:All sensor data"`
- Multiple topics: `"temp/#:temperatures:Temps;humidity/#:humidity:Humidity"`
- With wildcards: `"home/+/status:device_status:Device statuses"`

### Logging Configuration

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `LOG_LEVEL` | Logging level | `INFO` | `DEBUG`, `WARNING` |
| `LOG_FILE` | Log file path (optional) | `""` (stdout only) | `/app/logs/mqtt.log` |

### Alerting Configuration

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `ALERT_EMAIL_TO` | Email for alerts | `""` (disabled) | `admin@example.com` |
| `ALERT_DB_SIZE_MB` | DB size threshold (MB) | `""` (disabled) | `10000` (10GB) |
| `ALERT_FREE_SPACE_MB` | Free space threshold (MB) | `""` (disabled) | `2000` (2GB) |
| `ALERT_COOLDOWN_HOURS` | Hours between alerts | `24` | `12` or `48` |

**Startup Notification:** When `ALERT_EMAIL_TO` is configured, a success email is automatically sent when the container starts, confirming configuration and connectivity.

### System Configuration

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `TZ` | Timezone | `UTC` | `America/New_York` |

## Build Arguments (Email Alerts)

Configure SMTP at build time for email alerts:

| Argument | Description | Example |
|----------|-------------|---------|
| `SMTP_SERVER` | SMTP server hostname | `smtp.gmail.com` |
| `SMTP_PORT` | SMTP port | `587` |
| `SMTP_FROM` | From email address | `alerts@example.com` |
| `SMTP_TO` | Username (usually same as FROM) | `alerts@example.com` |
| `SMTP_PASSWORD` | SMTP password/app password | `your-app-password` |

## Common Usage Examples

### Christmas Tree Water Monitor 🎄

```bash
docker run -d \
  --name christmas-tree \
  --restart unless-stopped \
  -v $(pwd)/tree-data:/app/data \
  -v $(pwd)/tree-logs:/app/logs \
  -e TZ=America/New_York \
  -e MQTT_BROKER=192.168.1.100 \
  -e TOPICS="christmas/tree/water/#:water_level:Tree water level" \
  -e DB_PATH=/app/data/tree.db \
  -e ALERT_EMAIL_TO=you@example.com \
  -e ALERT_DB_SIZE_MB=100 \
  mqtt-logger

# Debug email issues:
tail -f tree-logs/msmtp.log
```

### Home Automation Sensors

```bash
docker run -d \
  --name home-sensors \
  --restart unless-stopped \
  -v /mnt/nas/mqtt-logs:/app/data \
  -e MQTT_BROKER=homeassistant.local \
  -e MQTT_USERNAME=mqtt \
  -e MQTT_PASSWORD=secretpass \
  -e TOPICS="home/+/temperature:temps:Temperatures;home/+/humidity:humidity:Humidity;home/+/motion:motion:Motion sensors" \
  -e DB_BATCH_SIZE=1000 \
  -e DB_FLUSH_INTERVAL=60 \
  mqtt-logger
```

### IoT Device Monitoring

```bash
docker run -d \
  --name iot-logger \
  --restart unless-stopped \
  -v $(pwd)/iot-data:/app/data \
  -e MQTT_BROKER=mqtt.myiot.com \
  -e MQTT_PORT=8883 \
  -e TOPICS="devices/+/status:status:Device status;devices/+/metrics:metrics:Device metrics" \
  -e LOG_LEVEL=DEBUG \
  -e LOG_FILE=/app/logs/iot.log \
  mqtt-logger
```

## Container Management

### View Logs
```bash
docker logs -f mqtt-logger
```

### Stop Container
```bash
docker stop mqtt-logger
```

### Start Container
```bash
docker start mqtt-logger
```

### Remove Container
```bash
docker stop mqtt-logger
docker rm mqtt-logger
```

### Update Container
```bash
# Pull new code, rebuild image
docker build -t mqtt-logger .

# Stop and remove old container
docker stop mqtt-logger
docker rm mqtt-logger

# Start new container with same settings
docker run -d --name mqtt-logger ... mqtt-logger
```

### Access Container Shell
```bash
docker exec -it mqtt-logger bash
```

### View Generated Config
```bash
docker exec mqtt-logger cat /app/config/mqtt_logger.toml
```

## Data Persistence

### Mount Points

Mount these directories to persist data:

```bash
-v $(pwd)/data:/app/data        # Database files (required)
-v $(pwd)/logs:/app/logs        # Log files (recommended for debugging)
```

**Important:** Always mount `/app/logs` to access:
- `msmtp.log` - Email/SMTP debugging information
- `mqtt_logger.log` - Application logs (if LOG_FILE is set)

### Backup Database

```bash
# Copy database from container
docker cp mqtt-logger:/app/data/mqtt_logs.db ./backup.db

# Or use volume mount
cp data/mqtt_logs.db backup-$(date +%Y%m%d).db
```

### Query Database

```bash
# Install DuckDB CLI on host
# Then query the database file directly
duckdb data/mqtt_logs.db "SELECT * FROM sensors LIMIT 10"

# Or use Docker
docker run --rm -v $(pwd)/data:/data \
  ghcr.io/duckdb/duckdb:latest \
  /data/mqtt_logs.db \
  "SELECT COUNT(*) FROM sensors"
```

## Networking

### Host Network Mode

If your MQTT broker is on localhost:

```bash
docker run -d \
  --name mqtt-logger \
  --network host \
  -v $(pwd)/data:/app/data \
  -e MQTT_BROKER=localhost \
  mqtt-logger
```

### Bridge Network (Default)

For remote brokers, use default bridge network:

```bash
docker run -d \
  --name mqtt-logger \
  -v $(pwd)/data:/app/data \
  -e MQTT_BROKER=mqtt.example.com \
  mqtt-logger
```

### Custom Network

```bash
# Create network
docker network create mqtt-network

# Run broker
docker run -d \
  --name mosquitto \
  --network mqtt-network \
  eclipse-mosquitto

# Run logger
docker run -d \
  --name mqtt-logger \
  --network mqtt-network \
  -v $(pwd)/data:/app/data \
  -e MQTT_BROKER=mosquitto \
  mqtt-logger
```

## Troubleshooting

### Check Configuration

```bash
docker exec mqtt-logger cat /app/config/mqtt_logger.toml
```

### View Logs

```bash
docker logs mqtt-logger
docker logs -f mqtt-logger  # Follow
docker logs --tail 100 mqtt-logger  # Last 100 lines
```

### Test MQTT Connection

```bash
# Install mosquitto clients
apt install mosquitto-clients

# Subscribe to test
mosquitto_sub -h mqtt.example.com -t '#' -v

# Publish test message
mosquitto_pub -h mqtt.example.com -t 'test/topic' -m 'test'
```

### Check Email Setup

```bash
# Check msmtp config
docker exec mqtt-logger cat /root/.msmtprc

# Test email using msmtp directly (most reliable)
docker exec mqtt-logger bash -c 'cat <<EOF | /usr/bin/msmtp -t
To: you@example.com
Subject: Test Email

This is a test
EOF'

# Or use the test script
./test-email-in-container.sh mqtt-logger you@example.com

# Check msmtp logs (from host - easier!)
tail -f logs/msmtp.log

# Or from inside container
docker exec mqtt-logger cat /app/logs/msmtp.log
```

### Database Issues

```bash
# Check database exists
docker exec mqtt-logger ls -lh /app/data/

# Check database integrity
docker exec mqtt-logger uv run python -c "
import duckdb
conn = duckdb.connect('/app/data/mqtt_logs.db')
print(conn.execute('PRAGMA integrity_check').fetchall())
"
```

### Container Won't Start

```bash
# Check container logs
docker logs mqtt-logger

# Check if port conflicts
docker ps -a

# Run interactively to debug
docker run --rm -it \
  -e MQTT_BROKER=mqtt.example.com \
  mqtt-logger \
  bash
```

## Performance Tuning

### For High-Volume MQTT

```bash
-e DB_BATCH_SIZE=10000 \
-e DB_FLUSH_INTERVAL=600
```

### For Low Latency

```bash
-e DB_BATCH_SIZE=100 \
-e DB_FLUSH_INTERVAL=10
```

### For SD Card / NAS Longevity

```bash
-e DB_BATCH_SIZE=5000 \
-e DB_FLUSH_INTERVAL=300
```

## Security

### Non-Root User (Future Enhancement)

Current implementation runs as root. To improve security in future versions:

```dockerfile
RUN adduser --disabled-password --gecos '' appuser
USER appuser
```

### Secrets Management

For production, use Docker secrets or environment files:

```bash
# Create env file
cat > mqtt.env <<EOF
MQTT_USERNAME=myuser
MQTT_PASSWORD=secretpassword
EOF

# Run with env file
docker run -d \
  --name mqtt-logger \
  --env-file mqtt.env \
  -v $(pwd)/data:/app/data \
  mqtt-logger

# Secure the env file
chmod 600 mqtt.env
```

## Multi-Architecture Support

Build for multiple architectures:

```bash
# Enable buildx
docker buildx create --use

# Build for multiple platforms
docker buildx build \
  --platform linux/amd64,linux/arm64,linux/arm/v7 \
  -t mqtt-logger:latest \
  --push \
  .
```

## Example: Running on Synology NAS

```bash
# Via Synology Docker UI:
# 1. Go to Registry, search for your image or build locally
# 2. Create container with these settings:
#    - Name: mqtt-logger
#    - Auto-restart: Yes
#    - Volume: /docker/mqtt-logger/data -> /app/data
#    - Environment variables: (add all required vars)

# Via SSH:
docker run -d \
  --name mqtt-logger \
  --restart unless-stopped \
  -v /volume1/docker/mqtt-logger/data:/app/data \
  -e MQTT_BROKER=192.168.1.100 \
  -e TOPICS="sensors/#:sensors:All sensors" \
  mqtt-logger
```

## Summary

- **Configuration**: 100% via environment variables
- **Persistence**: Mount `/app/data` for database
- **Email Alerts**: Set at build time with `--build-arg`
- **Multiple Topics**: Use semicolon-separated format
- **Restart Policy**: `--restart unless-stopped`
- **Timezone**: Set `TZ` environment variable

