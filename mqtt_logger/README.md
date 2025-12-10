# MQTT Logger

A robust, production-ready MQTT message logger that stores messages in a DuckDB database. Designed for reliable operation as a systemd service with automatic restarts and graceful shutdown handling.

Yes, this was vibe coded. It's for a yearly gag overengineered Christmas tree water level measurement project.

## Features

- 📡 **MQTT Support**: Subscribe to multiple topics with wildcard support (`+` and `#`)
- 💾 **Efficient Storage**: Uses DuckDB for fast, columnar storage of messages
- 🔄 **Auto-Reconnection**: Automatically reconnects to MQTT broker on connection loss
- 🚀 **High Performance**: Batched writes for optimal database performance
- 🛡️ **Production Ready**: Systemd integration with restart policies and graceful shutdown
- 🔧 **Flexible Configuration**: TOML-based configuration for all settings
- 📊 **Multiple Topics**: Support for logging different topics to different tables
- ✅ **Well Tested**: Comprehensive unit test coverage

## Requirements

- Python 3.11 or later
- uv package manager (recommended) or pip
- systemd (for service installation)

## Installation

### Development Setup

1. **Clone the repository:**

```bash
git clone https://github.com/yourusername/mqtt-logger.git
cd mqtt-logger
```

2. **Install uv (if not already installed):**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

3. **Install dependencies:**

```bash
uv sync
```

4. **Create configuration file:**

```bash
cp config/mqtt_logger.example.toml config/mqtt_logger.toml
# Edit config/mqtt_logger.toml with your settings
```

5. **Run the application:**

```bash
uv run python main.py config/mqtt_logger.toml
```

### Production Installation

For production deployment as a systemd service:

1. **Create a dedicated user:**

```bash
sudo useradd --system --shell /usr/sbin/nologin mqtt-logger
```

2. **Install the application:**

```bash
# Install to /opt/mqtt-logger
sudo mkdir -p /opt/mqtt-logger
sudo cp -r . /opt/mqtt-logger/
cd /opt/mqtt-logger

# Install dependencies using uv
sudo uv sync

# Create required directories
sudo mkdir -p /opt/mqtt-logger/data
sudo mkdir -p /opt/mqtt-logger/logs
sudo chown -R mqtt-logger:mqtt-logger /opt/mqtt-logger
```

3. **Configure the application:**

```bash
sudo cp config/mqtt_logger.example.toml config/mqtt_logger.toml
sudo nano config/mqtt_logger.toml  # Edit configuration
sudo chown mqtt-logger:mqtt-logger config/mqtt_logger.toml
```

4. **Install systemd service:**

```bash
# Copy service file
sudo cp mqtt-logger.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable service to start on boot
sudo systemctl enable mqtt-logger

# Start the service
sudo systemctl start mqtt-logger
```

5. **Verify the service is running:**

```bash
# Check service status
sudo systemctl status mqtt-logger

# View logs
sudo journalctl -u mqtt-logger -f
```

## Configuration

Configuration is specified in TOML format. See `config/mqtt_logger.example.toml` for a complete example.

### Email Alerting (Optional)

Monitor disk space and database size with email alerts:

```toml
[alerting]
email_to = "admin@example.com"           # Email address for alerts
db_size_threshold_mb = 1000              # Alert when DB exceeds 1GB
free_space_threshold_mb = 500            # Alert when < 500MB free
alert_cooldown_hours = 24                # Hours between repeat alerts
```

**Requirements:**
- System `mail` command configured (e.g., via `msmtp` package)
- All settings are optional and disabled by default
- Alerts are checked during periodic database flushes

**Example msmtp setup:**
```bash
# Install msmtp
sudo apt install msmtp msmtp-mta

# Configure ~/.msmtprc
account default
host smtp.gmail.com
port 587
from your-email@gmail.com
user your-email@gmail.com
password your-app-password
auth on
tls on
```

### MQTT Broker Settings

```toml
[mqtt]
broker = "mqtt.example.com"  # MQTT broker hostname
port = 1883                   # MQTT broker port
username = "user"             # Optional authentication
password = "pass"             # Optional authentication
client_id = ""                # Auto-generated if not specified
keepalive = 60                # Keep-alive interval in seconds
qos = 1                       # Quality of Service (0, 1, or 2)
```

### Database Settings

```toml
[database]
path = "data/mqtt_logs.db"   # Path to DuckDB database file
batch_size = 100              # Messages to batch before writing
flush_interval = 10           # Seconds between forced flushes
```

### Topic Configuration

Define multiple topics to log. Each topic pattern maps to a database table:

```toml
[[topics]]
pattern = "sensors/temperature/#"     # MQTT topic pattern
table_name = "temperature_sensors"    # Database table name
description = "Temperature readings"  # Optional description

[[topics]]
pattern = "devices/+/status"          # Single-level wildcard
table_name = "device_status"
description = "Device status messages"
```

**Topic Wildcards:**
- `+` matches a single level (e.g., `devices/+/status` matches `devices/1/status`)
- `#` matches multiple levels (e.g., `sensors/#` matches `sensors/temp/room1`)

### Logging Configuration

```toml
[logging]
level = "INFO"                                             # Log level
format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
file = "/opt/mqtt-logger/logs/mqtt_logger.log"            # Optional log file
```

### Alerting Configuration (Optional)

Monitor disk space and get email alerts:

```toml
[alerting]
email_to = "admin@example.com"        # Email for alerts (empty = disabled)
db_size_threshold_mb = 1000           # Alert when DB > 1GB (empty = disabled)
free_space_threshold_mb = 500         # Alert when < 500MB free (empty = disabled)
alert_cooldown_hours = 24             # Hours between repeat alerts
```

**Leave `email_to` empty to disable all alerting.**

## Usage

### Running Manually

```bash
# With default config location (config/mqtt_logger.toml)
uv run python main.py

# With custom config location
uv run python main.py /path/to/config.toml
```

### Managing the Systemd Service

```bash
# Start the service
sudo systemctl start mqtt-logger

# Stop the service
sudo systemctl stop mqtt-logger

# Restart the service
sudo systemctl restart mqtt-logger

# View service status
sudo systemctl status mqtt-logger

# View logs (live)
sudo journalctl -u mqtt-logger -f

# View logs (last 100 lines)
sudo journalctl -u mqtt-logger -n 100
```

### Querying Logged Data

You can query the DuckDB database using the DuckDB CLI or any DuckDB-compatible tool:

```bash
# Install DuckDB CLI
uv pip install duckdb

# Query the database
duckdb data/mqtt_logs.db
```

Example queries:

```sql
-- View recent messages
SELECT * FROM temperature_sensors
ORDER BY timestamp DESC
LIMIT 10;

-- Count messages per topic
SELECT topic, COUNT(*) as count
FROM temperature_sensors
GROUP BY topic;

-- Messages in the last hour
SELECT * FROM temperature_sensors
WHERE timestamp >= NOW() - INTERVAL '1 hour';

-- Average temperature by topic (example)
SELECT topic, AVG(CAST(payload AS DOUBLE)) as avg_temp
FROM temperature_sensors
WHERE topic LIKE 'sensors/temperature/%'
GROUP BY topic;
```

## Systemd Service Features

The systemd service includes:

- **Automatic Restart**: Service restarts on failure with exponential backoff
- **Rate Limiting**: Prevents infinite restart loops (5 restarts per 5 minutes)
- **Security Hardening**: Runs with restricted privileges and filesystem access
- **Resource Limits**: Memory and file descriptor limits
- **Logging**: Integrates with systemd journal

### Restart Policy

The service will automatically restart if it crashes, with the following policy:

- **Restart Delay**: 10 seconds between restarts
- **Burst Limit**: Maximum 5 restarts
- **Interval**: 300 seconds (5 minutes)

If the service fails 5 times within 5 minutes, systemd will stop attempting to restart it. This prevents infinite restart loops due to configuration errors.

## Development

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src --cov-report=html

# Run specific test file
uv run pytest tests/test_storage.py

# Run with verbose output
uv run pytest -v
```

### Code Quality

```bash
# Format code
uv run ruff format .

# Lint code
uv run ruff check .

# Fix linting issues
uv run ruff check --fix .
```

### Project Structure

```
mqtt-logger/
├── src/
│   └── mqtt_logger/
│       ├── __init__.py
│       ├── app.py           # Main application
│       ├── config.py        # Configuration management
│       ├── mqtt_client.py   # MQTT client
│       └── storage.py       # DuckDB storage
├── tests/
│   ├── test_app.py
│   ├── test_config.py
│   ├── test_mqtt_client.py
│   └── test_storage.py
├── config/
│   └── mqtt_logger.example.toml
├── main.py                  # Entry point
├── mqtt-logger.service      # Systemd service file
├── pyproject.toml           # Project configuration
└── README.md
```

## Troubleshooting

### Service Won't Start

1. **Check configuration:**
   ```bash
   sudo -u mqtt-logger cat /opt/mqtt-logger/config/mqtt_logger.toml
   ```

2. **Check permissions:**
   ```bash
   ls -la /opt/mqtt-logger
   ```

3. **View detailed logs:**
   ```bash
   sudo journalctl -u mqtt-logger -n 50 --no-pager
   ```

### Connection Issues

1. **Verify MQTT broker is accessible:**
   ```bash
   telnet mqtt.example.com 1883
   ```

2. **Check authentication credentials:**
   - Ensure username/password are correct
   - Verify ACL permissions on the MQTT broker

3. **Check firewall rules:**
   ```bash
   sudo iptables -L | grep 1883
   ```

### Database Issues

1. **Check database file permissions:**
   ```bash
   ls -la /opt/mqtt-logger/data/
   ```

2. **Verify disk space:**
   ```bash
   df -h /opt/mqtt-logger
   ```

3. **Check for corrupted database:**
   ```bash
   duckdb /opt/mqtt-logger/data/mqtt_logs.db "PRAGMA integrity_check;"
   ```

### High Memory Usage

- Reduce `batch_size` in configuration
- Decrease `flush_interval` for more frequent writes
- Add memory limits in systemd service (already set to 1G by default)

## Performance Tuning

- **Batch Size**: Larger batches improve write performance but use more memory
- **Flush Interval**: More frequent flushes reduce memory but increase I/O
- **QoS Level**: Lower QoS (0) improves throughput but may lose messages
- **Database Path**: Use SSD storage for better performance

### Raspberry Pi / SD Card Optimization

For devices with SD card storage, use these settings to minimize writes and extend card lifespan:

```toml
[database]
path = "data/mqtt_logs.db"
batch_size = 5000      # Larger batches = fewer writes
flush_interval = 300   # Less frequent writes (5 minutes)
```

**Trade-off:** Up to 5 minutes of data could be lost on unexpected shutdown, but SD card lifespan is dramatically extended (10+ years vs 6-12 months).

See [SD_CARD_OPTIMIZATION.md](SD_CARD_OPTIMIZATION.md) for detailed strategies including:
- Using tmpfs (RAM disk) for database
- System-wide SD card optimizations
- Backup strategies
- Write frequency calculations

## Security Considerations

- Store passwords securely (use environment variables or secrets management)
- Restrict file permissions on configuration files
- Use TLS for MQTT connections (port 8883)
- Run service with minimal privileges (enforced by systemd)
- Regularly update dependencies

## License

MIT License - see LICENSE file for details

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Submit a pull request

## Support

For issues and questions:
- Open an issue on GitHub
- Check existing issues for solutions
- Review logs with `journalctl -u mqtt-logger`

## Docker Deployment

Full Docker support with environment variable configuration! See [DOCKER.md](DOCKER.md) for complete guide.

**Quick start:**
```bash
# Build
docker build -t mqtt-logger .

# Run
docker run -d \
  --name mqtt-logger \
  --restart unless-stopped \
  -v $(pwd)/data:/app/data \
  -e MQTT_BROKER=mqtt.example.com \
  -e TOPICS="sensors/#:sensors:Sensor data" \
  mqtt-logger
```

## Roadmap

- [x] Docker container support
- [ ] TLS/SSL support for MQTT
- [ ] Web dashboard for viewing logs
- [ ] Export to other formats (CSV, JSON)
- [ ] Retention policies for old data
- [ ] Prometheus metrics export

