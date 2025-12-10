# Environment Variable Override System

## How It Works

The MQTT Logger uses a **two-tier configuration system**:

1. **Base Configuration (TOML file)** - Default values from config file
2. **Environment Variables** - Runtime overrides

When the application starts, it:
1. Loads the TOML config file
2. Checks for environment variables
3. **Overrides** TOML values with env vars if they exist

## Example

### Config File (`mqtt_logger.toml`)
```toml
[database]
path = "/app/data/mqtt_logs.db"
batch_size = 5000
flush_interval = 300
```

### Run with Override
```bash
docker run -d \
  -e DB_BATCH_SIZE=100 \
  -e DB_FLUSH_INTERVAL=10 \
  mqtt-logger
```

### Result
The application will use:
- `batch_size = 100` (from env var, overriding 5000)
- `flush_interval = 10` (from env var, overriding 300)
- `path = "/app/data/mqtt_logs.db"` (from TOML, not overridden)

## All Supported Environment Variables

### Database Settings
- `DB_PATH` - Database file path
- `DB_BATCH_SIZE` - Messages to batch before write
- `DB_FLUSH_INTERVAL` - Seconds between writes

### MQTT Settings
- `MQTT_BROKER` - Broker hostname
- `MQTT_PORT` - Broker port
- `MQTT_USERNAME` - Username for auth
- `MQTT_PASSWORD` - Password for auth
- `MQTT_CLIENT_ID` - Client identifier
- `MQTT_KEEPALIVE` - Keepalive interval (seconds)
- `MQTT_QOS` - Quality of Service (0, 1, or 2)

### Logging Settings
- `LOG_LEVEL` - Logging level (DEBUG, INFO, WARNING, ERROR)
- `LOG_FILE` - Log file path

### Alerting Settings
- `ALERT_EMAIL_TO` - Email address for alerts
- `ALERT_DB_SIZE_MB` - Database size threshold (MB)
- `ALERT_FREE_SPACE_MB` - Free space threshold (MB)
- `ALERT_COOLDOWN_HOURS` - Hours between repeat alerts

## Use Cases

### Quick Performance Tuning

Change batch/flush settings without rebuilding:

```bash
# Test with real-time settings
docker run -e DB_BATCH_SIZE=10 -e DB_FLUSH_INTERVAL=1 mqtt-logger

# If too aggressive, try balanced
docker stop mqtt-logger && docker rm mqtt-logger
docker run -e DB_BATCH_SIZE=100 -e DB_FLUSH_INTERVAL=10 mqtt-logger
```

### Environment-Specific Configuration

Use same image, different configs per environment:

```bash
# Development
docker run -e LOG_LEVEL=DEBUG -e DB_BATCH_SIZE=10 mqtt-logger

# Production
docker run -e LOG_LEVEL=INFO -e DB_BATCH_SIZE=5000 mqtt-logger
```

### Temporary Override for Testing

```bash
# Temporarily use test broker
docker run -e MQTT_BROKER=test.mosquitto.org mqtt-logger
```

## Priority Order

When a configuration value is set in multiple places:

1. **Environment Variable** (highest priority) ✅
2. **TOML Config File**
3. **Python Default Values** (lowest priority)

## Docker Compose Example

```yaml
services:
  mqtt-logger:
    image: mqtt-logger
    environment:
      # Override TOML values
      - DB_BATCH_SIZE=100
      - DB_FLUSH_INTERVAL=10
      - MQTT_BROKER=192.168.1.100
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
```

## Restart Not Required for Code Changes

Since env vars are read at Python startup (not just container startup), you can:

```bash
# Stop container
docker stop mqtt-logger

# Start with new env var (same image!)
docker run -e DB_BATCH_SIZE=50 mqtt-logger
```

No rebuild needed!

## Debugging

To see what values are being used:

```bash
# Check environment variables
docker exec mqtt-logger env | sort

# Check generated config (before overrides)
docker exec mqtt-logger cat /app/config/mqtt_logger.toml

# Check actual runtime values in logs
docker logs mqtt-logger | head -50
```

The Python code will log the actual values being used after env var overrides are applied.

## Best Practices

1. **Use TOML for stable defaults** - Put your standard config in the TOML file
2. **Use env vars for differences** - Override only what changes between environments
3. **Document your overrides** - In docker-compose.yml or run scripts
4. **Test before production** - Verify env vars are taking effect

## Implementation Details

The override happens in `src/mqtt_logger/config.py` in the `load_config()` function:

```python
# Load from TOML
db_data = data["database"]

# Override with env vars if present
if os.getenv("DB_BATCH_SIZE"):
    db_data["batch_size"] = int(os.getenv("DB_BATCH_SIZE"))
```

This means:
- ✅ Env vars checked every time Python starts
- ✅ No config file regeneration needed
- ✅ True runtime override capability

