# Data Sleigh

🎄 **Unified MQTT data collection and S3 upload with season awareness for Treelemetry**

Data Sleigh combines MQTT logging, YoLink sensor integration, DuckDB storage, S3 uploads, and intelligent season-aware behavior into a single Dockerized process.

## Features

- 📡 **Dual MQTT Support**: Local MQTT broker + YoLink cloud service
- 💾 **Efficient Storage**: DuckDB with optimized YoLink schema (normalized columns + raw JSON)
- 🔄 **Season Awareness**: Automatic behavior changes based on configured season dates
- ☁️ **S3 Integration**: Gzip-compressed JSON uploads for live website
- 📦 **Monthly Backups**: Automatic database archival during off-season
- 📧 **Email Alerts**: Low disk space and database size monitoring
- 🐳 **Docker Ready**: Complete containerization with environment variable configuration
- 🧪 **Well Tested**: Comprehensive test suite including season and backup tests

## Season-Aware Behavior

### In-Season Mode
- Collect MQTT + YoLink data to DuckDB
- Upload JSON to S3 every 30 seconds (configurable)
- JSON includes season dates for website validation
- Full aggregation and analysis

### Off-Season Mode
- Continue collecting MQTT + YoLink data to DuckDB
- **NO** JSON uploads to S3 (website stays static)
- Monthly database backup to S3
- Fresh database starts each month to free disk space

## Quick Start

### Docker (Recommended)

```bash
# Build
docker build -t data-sleigh .

# Run
docker run -d \
  --name data-sleigh \
  --restart unless-stopped \
  -v $(pwd)/data:/app/data \
  -e MQTT_BROKER=mqtt.example.com \
  -e TOPICS="xmas/tree/water/raw:water_level:Tree water level" \
  -e SEASON_START=2024-12-01 \
  -e SEASON_END=2025-01-15 \
  -e S3_BUCKET=your-bucket \
  -e AWS_ACCESS_KEY_ID=your-key \
  -e AWS_SECRET_ACCESS_KEY=your-secret \
  -e YOLINK_UAID=your-uaid \
  -e YOLINK_SECRET_KEY=your-secret \
  -e YOLINK_AIR_SENSOR_DEVICEID=d88b4c04000a9da6 \
  -e YOLINK_WATER_SENSOR_DEVICEID=d88b4c010008bbe2 \
  data-sleigh
```

### Local Development

```bash
# Install dependencies
uv sync

# Create configuration
cp config/data_sleigh.example.toml config/data_sleigh.toml
# Edit config/data_sleigh.toml with your settings

# Run
uv run python main.py config/data_sleigh.toml
```

## Configuration

### Environment Variables

**MQTT:**
- `MQTT_BROKER` - MQTT broker hostname
- `MQTT_PORT` - Port (default: 1883)
- `MQTT_USERNAME` / `MQTT_PASSWORD` - Authentication (optional)
- `TOPICS` - Topic patterns (format: `pattern1:table1:desc1;pattern2:table2:desc2`)

**Database:**
- `DB_PATH` - DuckDB file path (default: `/app/data/mqtt_logs.db`)
- `DB_BATCH_SIZE` - Messages to batch (default: 5000)
- `DB_FLUSH_INTERVAL` - Flush interval in seconds (default: 300)

**Season:**
- `SEASON_START` - Season start date (format: YYYY-MM-DD)
- `SEASON_END` - Season end date (format: YYYY-MM-DD)

**S3:**
- `S3_BUCKET` - S3 bucket name (required)
- `S3_JSON_KEY` - JSON object key (default: water-level.json)
- `S3_BACKUP_PREFIX` - Backup prefix (default: backups/)
- `AWS_ACCESS_KEY_ID` - AWS access key (required)
- `AWS_SECRET_ACCESS_KEY` - AWS secret key (required)

**Upload:**
- `UPLOAD_INTERVAL_SECONDS` - Upload frequency during season (default: 30)
- `MINUTES_OF_DATA` - Minutes of history in JSON (default: 10)
- `REPLAY_DELAY_SECONDS` - Replay delay for visualization (default: 300)

**Backup:**
- `BACKUP_DAY_OF_MONTH` - Day to run backup (default: 1)
- `BACKUP_HOUR` - Hour to run backup (default: 3)

**YoLink (optional):**
- `YOLINK_UAID` - YoLink User Access ID
- `YOLINK_SECRET_KEY` - YoLink Secret Key
- `YOLINK_AIR_SENSOR_DEVICEID` - Air sensor device ID
- `YOLINK_WATER_SENSOR_DEVICEID` - Water sensor device ID

**Email Alerts (optional):**
- `ALERT_EMAIL_TO` - Email address for alerts
- `ALERT_DB_SIZE_MB` - Database size threshold
- `ALERT_FREE_SPACE_MB` - Free space threshold

## YoLink Data Improvements

### Before (mqtt_logger)
```sql
-- Hard to query - JSON extraction required
SELECT json_extract(payload, '$.temperature') FROM yolink_sensors
```

### After (data_sleigh)
```sql
-- Easy to query - normalized columns
SELECT device_type, temperature, humidity, battery
FROM yolink_sensors
WHERE device_type = 'air' AND temperature > 70
```

**Schema:**
- `device_id` - YoLink device ID
- `device_type` - 'air' or 'water'
- `temperature` - Temperature (Fahrenheit)
- `humidity` - Humidity percentage (NULL for water sensors)
- `battery` - Battery level (0-100)
- `signal` - Signal strength (dBm)
- `raw_json` - Complete event data (for debugging)

## Development Tools

### Generate JSON Output

```bash
# Generate JSON from database (for testing)
python tools/generate_json.py data/mqtt_logs.db output.json

# With custom season dates
python tools/generate_json.py data/mqtt_logs.db \
  --season-start 2024-12-01 \
  --season-end 2025-01-15
```

### Generate Sample Data

```bash
# Create test database with 7 days of data
python tools/create_sample_data.py test.duckdb 7

# Test with generated data
python tools/generate_json.py test.duckdb
```

## Testing

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src --cov-report=html

# Run specific test file
uv run pytest tests/test_season_behavior.py
```

## Monitoring

### Logs

```bash
# Docker
docker logs -f data-sleigh

# Look for:
# - "IN-SEASON" or "OFF-SEASON" mode indicator
# - Upload success/skip messages
# - Monthly backup notifications
# - Email alert confirmations
```

### Health Checks

- **Database size**: Monitor disk usage alerts
- **S3 uploads**: Check bucket for recent JSON updates (during season)
- **Backups**: Verify monthly backups in S3 `backups/` prefix (off-season)

## Architecture

### Components

```
data_sleigh/
├── app.py              # Main orchestrator with season-aware loops
├── config.py           # Configuration with season/S3/backup sections
├── mqtt_client.py      # Local MQTT client
├── yolink_client.py    # YoLink cloud MQTT client
├── storage.py          # DuckDB with normalized YoLink schema
├── aggregator.py       # Data aggregation functions
├── analyzer.py         # Segment analysis for predictions
├── uploader.py         # S3 upload with gzip compression
├── backup.py           # Monthly database backup manager
└── alerting.py         # Email alerts for disk monitoring
```

### Data Flow

```
Local MQTT → storage.py → DuckDB
YoLink MQTT → storage.py → DuckDB (normalized)
                    ↓
            [Season Check]
                    ↓
        ┌───────────┴───────────┐
        ↓                       ↓
   IN-SEASON              OFF-SEASON
        ↓                       ↓
  aggregator.py          [Wait for backup day]
  analyzer.py                  ↓
        ↓                  backup.py
  uploader.py                  ↓
        ↓                  S3 (backups/)
   S3 (JSON)              Fresh DuckDB
```

## Migration from mqtt_logger + uploader

Data Sleigh consolidates the separate `mqtt_logger` and `uploader` components:

**Benefits:**
- ✅ Eliminates DuckDB locking issues (single process)
- ✅ Simplified deployment (one container vs two)
- ✅ Season-aware behavior built-in
- ✅ Improved YoLink schema (normalized columns)
- ✅ Monthly backups during off-season
- ✅ Consistent configuration pattern

**Migration steps:**
1. Deploy `data_sleigh` with your existing configuration
2. Test with sample data or parallel deployment
3. Switch DNS/routing to new deployment
4. Remove old `mqtt_logger` and `uploader` containers

## Troubleshooting

### Database locked errors
- Not possible in data_sleigh (single process)
- If you see them, check for conflicting processes

### No JSON uploads during season
- Check `docker logs` for season mode (should show "IN-SEASON")
- Verify `SEASON_START` and `SEASON_END` environment variables
- Check current date is between season dates

### YoLink data not appearing
- Verify `YOLINK_UAID` and `YOLINK_SECRET_KEY` are set
- Check device IDs match your sensors
- Look for "YoLink client started" in logs

### Monthly backup not running
- Verify you're in OFF-SEASON mode
- Check `BACKUP_DAY_OF_MONTH` and `BACKUP_HOUR` settings
- Look for "Starting monthly backup" in logs

## AWS Credential Generation

For generating AWS credentials for S3 access, see the `uploader/` folder which contains:
- AWS CDK infrastructure code
- IAM policy generation
- Credential creation scripts

Reference: `../uploader/README.md` for AWS setup instructions.

## License

MIT License - see LICENSE file for details

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Submit a pull request

## Support

For issues and questions:
- Check logs with `docker logs data-sleigh`
- Review configuration in generated TOML file
- Verify season dates and current mode
- Check S3 bucket permissions


