# Quick Start Guide

## Installation

1. Install dependencies:
```bash
uv sync --all-extras
```

2. Create configuration:
```bash
cp config/mqtt_logger.example.toml config/mqtt_logger.toml
```

3. Edit `config/mqtt_logger.toml` with your MQTT broker details

## Running Locally

```bash
# Run the logger
uv run python main.py

# Or with custom config path
uv run python main.py /path/to/config.toml
```

## Running with Docker

```bash
# Build image
docker build -t mqtt-logger .

# Run container
docker run -d \
  --name mqtt-logger \
  --restart unless-stopped \
  -v $(pwd)/data:/app/data \
  -e MQTT_BROKER=mqtt.example.com \
  -e TOPICS="sensors/#:sensors:Sensor data" \
  mqtt-logger

# View logs
docker logs -f mqtt-logger
```

See [DOCKER.md](DOCKER.md) for complete Docker documentation.

## Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src --cov-report=html

# Run specific test file
uv run pytest tests/test_storage.py -v
```

## Production Deployment

### Quick Install on Linux

```bash
# 1. Create user
sudo useradd --system --shell /usr/sbin/nologin mqtt-logger

# 2. Install to /opt
sudo mkdir -p /opt/mqtt-logger
sudo cp -r . /opt/mqtt-logger/
cd /opt/mqtt-logger

# 3. Install dependencies
sudo uv sync

# 4. Configure
sudo cp config/mqtt_logger.example.toml config/mqtt_logger.toml
sudo nano config/mqtt_logger.toml

# 5. Create directories
sudo mkdir -p /opt/mqtt-logger/{data,logs}
sudo chown -R mqtt-logger:mqtt-logger /opt/mqtt-logger

# 6. Install systemd service
sudo cp mqtt-logger.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable mqtt-logger
sudo systemctl start mqtt-logger

# 7. Check status
sudo systemctl status mqtt-logger
sudo journalctl -u mqtt-logger -f
```

## Configuration Examples

### Raspberry Pi / SD Card Configuration

For Raspberry Pi or devices with SD card storage (recommended to minimize writes):

```toml
[mqtt]
broker = "mqtt.example.com"
port = 1883
qos = 1

[database]
path = "data/mqtt_logs.db"
batch_size = 5000      # Large batches = fewer writes
flush_interval = 300   # Write every 5 minutes

[[topics]]
pattern = "sensors/#"
table_name = "all_sensors"

[logging]
level = "INFO"
# No file = journal only (no SD writes)
```

**Benefits:** Minimal SD card wear, 10+ year lifespan  
**Trade-off:** Up to 5 minutes of data loss on crash

See [SD_CARD_OPTIMIZATION.md](SD_CARD_OPTIMIZATION.md) for more details.

### Basic Configuration

```toml
[mqtt]
broker = "mqtt.example.com"
port = 1883
qos = 1

[database]
path = "data/mqtt_logs.db"

[[topics]]
pattern = "sensors/#"
table_name = "all_sensors"
```

### With Authentication

```toml
[mqtt]
broker = "mqtt.example.com"
port = 1883
username = "myuser"
password = "mypassword"
qos = 1

[database]
path = "data/mqtt_logs.db"

[[topics]]
pattern = "home/+/temperature"
table_name = "temperatures"

[[topics]]
pattern = "home/+/humidity"
table_name = "humidity"
```

### With Email Alerts

```toml
[mqtt]
broker = "mqtt.example.com"
port = 1883

[database]
path = "data/mqtt_logs.db"
batch_size = 5000
flush_interval = 300

[[topics]]
pattern = "sensors/#"
table_name = "sensors"

[alerting]
email_to = "admin@example.com"
db_size_threshold_mb = 10000      # Alert when DB > 10GB
free_space_threshold_mb = 2000    # Alert when < 2GB free
alert_cooldown_hours = 24
```

**Requires:** System `mail` command (via msmtp). See [ALERTING.md](ALERTING.md) for setup.

## Querying Data

```bash
# Open database
duckdb data/mqtt_logs.db

# View recent messages
SELECT * FROM all_sensors ORDER BY timestamp DESC LIMIT 10;

# Count by topic
SELECT topic, COUNT(*) FROM all_sensors GROUP BY topic;

# Messages in last hour
SELECT * FROM all_sensors 
WHERE timestamp >= NOW() - INTERVAL '1 hour';
```

## Troubleshooting

### Check logs
```bash
sudo journalctl -u mqtt-logger -n 100
```

### Test MQTT connection
```bash
# Install mosquitto clients
sudo apt install mosquitto-clients

# Subscribe to topic
mosquitto_sub -h mqtt.example.com -t '#' -v

# Publish test message
mosquitto_pub -h mqtt.example.com -t 'test/topic' -m 'test message'
```

### Verify database
```bash
ls -lh data/
duckdb data/mqtt_logs.db "SELECT COUNT(*) FROM all_sensors;"
```

## Development

### Code formatting
```bash
uv run ruff format .
```

### Linting
```bash
uv run ruff check .
uv run ruff check --fix .
```

### Add new dependency
```bash
uv add package-name
```

### Update dependencies
```bash
uv lock --upgrade
uv sync
```

