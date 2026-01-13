# Data Sleigh Deployment Guide

Complete guide for deploying Data Sleigh in production.

## Prerequisites

- Docker or Docker Compose
- MQTT broker (Mosquitto, etc.)
- AWS account with S3 access
- YoLink account (optional, for YoLink sensors)
- SMTP server for email alerts (optional)

## Docker Deployment

### Basic Deployment

```bash
# Build the image
docker build -t data-sleigh:latest .

# Run with minimal configuration
docker run -d \
  --name data-sleigh \
  --restart unless-stopped \
  -v /path/to/data:/app/data \
  -e MQTT_BROKER=mqtt.local \
  -e TOPICS="sensors/#:sensor_data:All sensors" \
  -e SEASON_START=2024-12-01 \
  -e SEASON_END=2025-01-15 \
  -e S3_BUCKET=my-bucket \
  -e AWS_ACCESS_KEY_ID=AKIAXXXXXX \
  -e AWS_SECRET_ACCESS_KEY=xxxxxxxx \
  data-sleigh:latest
```

### Full Configuration with Email Alerts

```bash
docker run -d \
  --name data-sleigh \
  --restart unless-stopped \
  -v /path/to/data:/app/data \
  -v /path/to/logs:/app/logs \
  -e MQTT_BROKER=mqtt.local \
  -e MQTT_PORT=1883 \
  -e MQTT_USERNAME=user \
  -e MQTT_PASSWORD=pass \
  -e TOPICS="xmas/tree/water/raw:water_level:Tree water;sensors/#:sensors:All sensors" \
  -e DB_PATH=/app/data/mqtt_logs.db \
  -e DB_BATCH_SIZE=5000 \
  -e DB_FLUSH_INTERVAL=300 \
  -e LOG_LEVEL=INFO \
  -e ALERT_EMAIL_TO=admin@example.com \
  -e ALERT_DB_SIZE_MB=1000 \
  -e ALERT_FREE_SPACE_MB=500 \
  -e SEASON_START=2024-12-01 \
  -e SEASON_END=2025-01-15 \
  -e S3_BUCKET=treelemetry-data \
  -e S3_JSON_KEY=water-level.json \
  -e S3_BACKUP_PREFIX=backups/ \
  -e AWS_ACCESS_KEY_ID=AKIAXXXXXX \
  -e AWS_SECRET_ACCESS_KEY=xxxxxxxx \
  -e UPLOAD_INTERVAL_SECONDS=30 \
  -e MINUTES_OF_DATA=10 \
  -e BACKUP_DAY_OF_MONTH=1 \
  -e BACKUP_HOUR=3 \
  -e YOLINK_UAID=your-uaid \
  -e YOLINK_SECRET_KEY=your-secret \
  -e YOLINK_AIR_SENSOR_DEVICEID=d88b4c04000a9da6 \
  -e YOLINK_WATER_SENSOR_DEVICEID=d88b4c010008bbe2 \
  -e TZ=America/New_York \
  data-sleigh:latest
```

## Docker Compose Deployment

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  data-sleigh:
    build: .
    container_name: data-sleigh
    restart: unless-stopped
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    environment:
      # MQTT Configuration
      MQTT_BROKER: mqtt.local
      MQTT_PORT: 1883
      MQTT_USERNAME: user
      MQTT_PASSWORD: pass
      TOPICS: "xmas/tree/water/raw:water_level:Tree water level;sensors/#:sensors:All sensors"

      # Database Configuration
      DB_PATH: /app/data/mqtt_logs.db
      DB_BATCH_SIZE: 5000
      DB_FLUSH_INTERVAL: 300

      # Season Configuration
      SEASON_START: "2024-12-01"
      SEASON_END: "2025-01-15"

      # S3 Configuration
      S3_BUCKET: treelemetry-data
      S3_JSON_KEY: water-level.json
      S3_BACKUP_PREFIX: backups/
      AWS_ACCESS_KEY_ID: ${AWS_ACCESS_KEY_ID}
      AWS_SECRET_ACCESS_KEY: ${AWS_SECRET_ACCESS_KEY}

      # Upload Configuration
      UPLOAD_INTERVAL_SECONDS: 30
      MINUTES_OF_DATA: 10
      REPLAY_DELAY_SECONDS: 300

      # Backup Configuration
      BACKUP_DAY_OF_MONTH: 1
      BACKUP_HOUR: 3

      # YoLink Configuration (optional)
      YOLINK_UAID: ${YOLINK_UAID}
      YOLINK_SECRET_KEY: ${YOLINK_SECRET_KEY}
      YOLINK_AIR_SENSOR_DEVICEID: d88b4c04000a9da6
      YOLINK_WATER_SENSOR_DEVICEID: d88b4c010008bbe2

      # Email Alerts (optional)
      ALERT_EMAIL_TO: admin@example.com
      ALERT_DB_SIZE_MB: 1000
      ALERT_FREE_SPACE_MB: 500
      ALERT_COOLDOWN_HOURS: 24

      # Timezone
      TZ: America/New_York

    # Optional: Depends on local MQTT broker
    depends_on:
      - mqtt

  mqtt:
    image: eclipse-mosquitto:2
    container_name: mqtt
    restart: unless-stopped
    ports:
      - "1883:1883"
    volumes:
      - ./mosquitto/config:/mosquitto/config
      - ./mosquitto/data:/mosquitto/data
      - ./mosquitto/log:/mosquitto/log
```

Create `.env` file for secrets:

```bash
AWS_ACCESS_KEY_ID=AKIAXXXXXX
AWS_SECRET_ACCESS_KEY=xxxxxxxx
YOLINK_UAID=your-uaid
YOLINK_SECRET_KEY=your-secret
```

Deploy:

```bash
docker-compose up -d
```

## Email Alerts Setup

### Build with SMTP Configuration

For email alerts, build the Docker image with SMTP build arguments:

```bash
docker build \
  --build-arg SMTP_SERVER=smtp.gmail.com \
  --build-arg SMTP_PORT=587 \
  --build-arg SMTP_FROM=alerts@example.com \
  --build-arg SMTP_TO=admin@example.com \
  --build-arg SMTP_PASSWORD="your-app-password" \
  -t data-sleigh:latest .
```

Then set the alert email in runtime environment:

```bash
docker run ... -e ALERT_EMAIL_TO=admin@example.com ...
```

## AWS S3 Setup

### 1. Create S3 Bucket

```bash
aws s3 mb s3://treelemetry-data --region us-east-1
```

### 2. Configure Bucket Policy for Public Read

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PublicReadGetObject",
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::treelemetry-data/water-level.json"
    }
  ]
}
```

Apply:

```bash
aws s3api put-bucket-policy \
  --bucket treelemetry-data \
  --policy file://bucket-policy.json
```

### 3. Create IAM User with S3 Access

```bash
# Create user
aws iam create-user --user-name data-sleigh

# Attach policy
aws iam attach-user-policy \
  --user-name data-sleigh \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess

# Create access key
aws iam create-access-key --user-name data-sleigh
```

Or use the CDK infrastructure in `../uploader/`:

```bash
cd ../uploader/infrastructure
cdk deploy
```

### 4. Enable S3 CORS (for website)

```json
[
  {
    "AllowedHeaders": ["*"],
    "AllowedMethods": ["GET", "HEAD"],
    "AllowedOrigins": ["*"],
    "ExposeHeaders": ["ETag"]
  }
]
```

Apply:

```bash
aws s3api put-bucket-cors \
  --bucket treelemetry-data \
  --cors-configuration file://cors.json
```

## Monitoring

### View Logs

```bash
# Real-time logs
docker logs -f data-sleigh

# Last 100 lines
docker logs --tail 100 data-sleigh

# Filter for errors
docker logs data-sleigh 2>&1 | grep ERROR
```

### Check Status

```bash
# Container status
docker ps | grep data-sleigh

# Resource usage
docker stats data-sleigh

# Database size
docker exec data-sleigh ls -lh /app/data/mqtt_logs.db
```

### Verify Uploads

```bash
# Check last S3 upload time (during season)
aws s3api head-object \
  --bucket treelemetry-data \
  --key water-level.json \
  --query 'LastModified'

# List backups (off-season)
aws s3 ls s3://treelemetry-data/backups/
```

## Maintenance

### Update Season Dates

```bash
# Stop container
docker stop data-sleigh

# Update and restart with new dates
docker run -d \
  --name data-sleigh \
  ... \
  -e SEASON_START=2025-12-01 \
  -e SEASON_END=2026-01-15 \
  data-sleigh:latest

# Or with docker-compose
# Edit docker-compose.yml, then:
docker-compose up -d
```

### Manual Backup

```bash
# Enter container
docker exec -it data-sleigh /bin/bash

# Inside container, use Python
python3 <<EOF
from pathlib import Path
from data_sleigh.backup import BackupManager
from data_sleigh.config import BackupConfig, S3Config
from data_sleigh.storage import MessageStore

backup_config = BackupConfig(day_of_month=1, hour=3)
s3_config = S3Config(
    bucket="treelemetry-data",
    backup_prefix="backups/",
    aws_access_key_id="...",
    aws_secret_access_key="..."
)

manager = BackupManager(backup_config, s3_config)
store = MessageStore("/app/data/mqtt_logs.db")
manager.backup_database(Path("/app/data/mqtt_logs.db"), store)
EOF
```

### Database Maintenance

```bash
# Check database size
docker exec data-sleigh du -h /app/data/mqtt_logs.db

# Query database
docker exec -it data-sleigh /bin/bash
uv run python3 <<EOF
import duckdb
conn = duckdb.connect('/app/data/mqtt_logs.db', read_only=True)
print(conn.execute("SELECT COUNT(*) FROM water_level").fetchone())
print(conn.execute("SELECT COUNT(*) FROM yolink_sensors").fetchone())
conn.close()
EOF
```

## Troubleshooting

### Container Won't Start

```bash
# Check logs for errors
docker logs data-sleigh

# Verify configuration
docker exec data-sleigh cat /app/config/data_sleigh.toml

# Test database access
docker exec data-sleigh ls -la /app/data/
```

### MQTT Connection Issues

```bash
# Test MQTT broker connectivity
docker exec data-sleigh ping -c 3 mqtt.local

# Check MQTT credentials
docker exec data-sleigh env | grep MQTT
```

### S3 Upload Failures

```bash
# Verify AWS credentials
docker exec data-sleigh env | grep AWS

# Test S3 access
docker exec data-sleigh aws s3 ls s3://treelemetry-data/

# Check season mode
docker logs data-sleigh | grep -i season
```

### YoLink Not Working

```bash
# Verify credentials
docker exec data-sleigh env | grep YOLINK

# Check YoLink client logs
docker logs data-sleigh | grep -i yolink

# Verify device IDs are correct
```

### Email Alerts Not Sending

```bash
# Check msmtp configuration
docker exec data-sleigh cat /root/.msmtprc

# Test email manually
docker exec data-sleigh /bin/bash -c 'echo "Test" | mail -s "Test" admin@example.com'

# Check alert email is set
docker exec data-sleigh env | grep ALERT_EMAIL_TO
```

## Backup and Recovery

### Restore from Backup

```bash
# List available backups
aws s3 ls s3://treelemetry-data/backups/

# Download backup
aws s3 cp s3://treelemetry-data/backups/mqtt_logs_backup_2025-01.duckdb \
  ./mqtt_logs.db

# Copy to container volume
docker cp mqtt_logs.db data-sleigh:/app/data/mqtt_logs.db

# Restart container
docker restart data-sleigh
```

### Export Data

```bash
# Export to JSON
docker exec data-sleigh \
  uv run python tools/generate_json.py \
  /app/data/mqtt_logs.db \
  /app/data/export.json

# Copy from container
docker cp data-sleigh:/app/data/export.json ./export.json
```

## Security Best Practices

1. **Secrets Management**: Use Docker secrets or AWS Secrets Manager
2. **Network**: Run on private network, expose only necessary ports
3. **IAM**: Use least-privilege IAM policies
4. **Backups**: Encrypt backups with S3 server-side encryption
5. **Updates**: Regularly update base image and dependencies
6. **Monitoring**: Set up CloudWatch alarms for S3 access

## Performance Tuning

### For High-Frequency Data

```bash
-e DB_BATCH_SIZE=10000 \
-e DB_FLUSH_INTERVAL=600 \
-e UPLOAD_INTERVAL_SECONDS=60
```

### For Low-Frequency Data

```bash
-e DB_BATCH_SIZE=100 \
-e DB_FLUSH_INTERVAL=30 \
-e UPLOAD_INTERVAL_SECONDS=15
```

### For SD Card / Raspberry Pi

```bash
-e DB_BATCH_SIZE=5000 \
-e DB_FLUSH_INTERVAL=300
```

## Scaling

Data Sleigh is designed for single-instance deployment. For scaling:

1. **Horizontal**: Deploy multiple instances with different MQTT topics
2. **Vertical**: Increase container memory/CPU limits
3. **Storage**: Use external volume with more space
4. **Database**: Consider separate DuckDB files per topic

## Support

For deployment issues:
- Check logs: `docker logs data-sleigh`
- Verify configuration: `docker exec data-sleigh cat /app/config/data_sleigh.toml`
- Test connectivity: MQTT, S3, YoLink
- Review season mode: Check if behavior matches expectation



