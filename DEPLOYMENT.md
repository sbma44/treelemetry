# Deployment Guide

Complete deployment instructions for Treelemetry.

## Prerequisites

- AWS CLI configured with admin permissions
- Python 3.11+ with `uv` installed
- Node.js 18+ with npm (for CDK CLI via `npx` and Vite)
- Docker installed
- MQTT broker (e.g., Mosquitto) running and accessible
- IoT sensors publishing to MQTT topics

## Overview

The deployment process has four main steps:

1. **MQTT Logger** - Set up data collection from IoT sensors
2. **Infrastructure** - Deploy AWS resources (S3 bucket, IAM credentials)
3. **Uploader** - Set up data aggregation and S3 upload daemon
4. **Static Site** - Build and deploy visualization dashboard

## Step 1: Deploy MQTT Logger

The MQTT Logger captures sensor data and stores it in DuckDB. This must be set up first as it creates the database that the uploader will read from.

See [`mqtt_logger/README.md`](mqtt_logger/README.md) and [`mqtt_logger/QUICKSTART.md`](mqtt_logger/QUICKSTART.md) for complete documentation.

### Quick Start with Docker:

```bash
cd mqtt_logger
docker build -t mqtt-logger .

# Run with environment variables
docker run -d \
  --name mqtt-logger \
  --restart unless-stopped \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  -e MQTT_BROKER=mqtt.example.com \
  -e MQTT_USERNAME=user \
  -e MQTT_PASSWORD=pass \
  -e TOPICS="xmas/tree/water/raw:water_level:Water level readings" \
  mqtt-logger
```

**Verify it's working:**

```bash
# Check logs
docker logs -f mqtt-logger

# Check database is being created
ls -lh mqtt_logger/data/mqtt_logs.db

# Query the database
duckdb mqtt_logger/data/mqtt_logs.db "SELECT COUNT(*) FROM water_level"
```

### Alternative: systemd Service

For production deployments on Linux:

```bash
cd mqtt_logger
# Follow instructions in QUICKSTART.md for systemd setup
sudo systemctl enable mqtt-logger
sudo systemctl start mqtt-logger
sudo journalctl -u mqtt-logger -f
```

## Step 2: Deploy Infrastructure

Deploy the AWS CDK stack to create S3 bucket and IAM credentials:

```bash
cd infrastructure
uv sync
npx aws-cdk bootstrap  # First time only
npx aws-cdk deploy
```

Note: `npx` downloads and runs the CDK CLI without requiring a global install.

**Save the outputs!** You'll need:
- `AccessKeyId`: AWS access key ID
- `SecretAccessKey`: AWS secret access key

The bucket name is fixed at `treelemetry-sbma44-water-data` and already configured everywhere.

## Step 3: Verify the Bucket

The CDK deployment created the bucket `treelemetry-sbma44-water-data`. You can verify:

```bash
aws s3 ls s3://treelemetry-sbma44-water-data/
```

Build the static site:

```bash
cd site
npm install
npm run build
```

The built site is now in the `docs/` directory.

## Step 4: Deploy to GitHub Pages

Commit and push everything to GitHub:

```bash
git add .
git commit -m "Initial deployment"
git push origin main
```

Enable GitHub Pages:

1. Go to your repository on GitHub
2. Navigate to Settings → Pages
3. Under "Source", select "Deploy from a branch"
4. Select `main` branch and `/docs` folder
5. Click "Save"

## Step 5: Set Up the Uploader

The uploader reads from the DuckDB database created by the MQTT Logger and uploads aggregated data to S3.

**Important:** The uploader should mount the database file as **read-only** (`:ro`) to prevent lock conflicts with the MQTT Logger.

Create an environment file for the uploader:

```bash
cd uploader
cp env.example .env
```

Edit `.env` with your credentials:

```bash
# Point to the database created by mqtt_logger
DUCKDB_PATH=/absolute/path/to/mqtt_logger/data/mqtt_logs.db
S3_BUCKET=treelemetry-sbma44-water-data
S3_KEY=water-level.json
AWS_ACCESS_KEY_ID=xxx       # From CDK output
AWS_SECRET_ACCESS_KEY=yyy   # From CDK output
MINUTES_OF_DATA=10
REPLAY_DELAY_SECONDS=300
UPLOAD_INTERVAL_SECONDS=30
```

## Step 6: Run the Uploader

### Option A: Docker (Recommended)

Build the Docker image:

```bash
cd uploader
docker build -t treelemetry-uploader .
```

Run as a long-running daemon:

```bash
docker run -d \
  --name treelemetry-uploader \
  --restart unless-stopped \
  -e AWS_ACCESS_KEY_ID=xxx \
  -e AWS_SECRET_ACCESS_KEY=yyy \
  -v /absolute/path/to/mqtt_logs.db:/data/tree.duckdb:ro \
  treelemetry-uploader
```

The container runs continuously, uploading every 30 seconds (configurable with `UPLOAD_INTERVAL_SECONDS`).

**Monitor logs:**
```bash
docker logs -f treelemetry-uploader
```

**Stop the uploader:**
```bash
docker stop treelemetry-uploader
```

**Restart after config change:**
```bash
docker stop treelemetry-uploader
docker rm treelemetry-uploader
# Run docker run command again with new settings
```

### Option B: Docker Compose (Easiest)

Create a `.env` file in the project root:

```bash
AWS_ACCESS_KEY_ID=xxx
AWS_SECRET_ACCESS_KEY=yyy
DUCKDB_PATH=/absolute/path/to/mqtt_logs.db
UPLOAD_INTERVAL_SECONDS=30
```

Start the service:

```bash
docker-compose up -d
```

View logs:

```bash
docker-compose logs -f uploader
```

Stop the service:

```bash
docker-compose down
```

## Step 7: Monitoring

### Monitor MQTT Logger

Check that sensor data is being captured:

```bash
# Docker logs
docker logs -f mqtt-logger

# Or with systemd
sudo journalctl -u mqtt-logger -f

# Check database growth
watch -n 5 'ls -lh mqtt_logger/data/mqtt_logs.db'

# Query recent data
duckdb mqtt_logger/data/mqtt_logs.db "SELECT COUNT(*), MAX(timestamp) FROM water_level"
```

### Monitor Uploader

The uploader runs as a long-running daemon. No cron or systemd timers needed!

Check logs to ensure it's working:

```bash
# View Docker logs
docker logs -f treelemetry-uploader

# Or with docker-compose
docker-compose logs -f uploader
```

You should see output like:
```
🎄 Treelemetry Uploader Starting
   Upload Interval: 30 seconds
[2025-12-06 12:00:00] Upload #1
  Retrieved 200 measurements
  ✓ Upload complete in 0.5s
```

Verify the JSON file is accessible:

```bash
curl https://treelemetry-sbma44-water-data.s3.amazonaws.com/water-level.json
```

## Updating the Site

To update the static site:

```bash
cd site
npm run build
git add ../docs
git commit -m "Update site"
git push origin main
```

GitHub Pages will automatically deploy the changes.

## Monitoring

Check uploader logs:

```bash
# Docker
docker logs treelemetry-uploader

# Systemd
sudo journalctl -u treelemetry-uploader.service -f
```

Verify the JSON file is being updated:

```bash
curl https://your-bucket.s3.amazonaws.com/water-level.json
```

## Troubleshooting

### MQTT Logger Not Receiving Data

**Check MQTT broker connectivity:**
```bash
# Test connection to MQTT broker
mosquitto_sub -h mqtt.example.com -t '#' -v

# Check if the logger is subscribed
docker logs mqtt-logger | grep "Subscribed to"
```

**Check topic patterns:**
- Ensure topic patterns in config match your sensor topics
- Use `#` for multi-level wildcard, `+` for single-level
- Verify sensors are publishing to the expected topics

**Check database:**
```bash
# Verify database file exists and is growing
ls -lh mqtt_logger/data/mqtt_logs.db

# Check if tables were created
duckdb mqtt_logger/data/mqtt_logs.db ".tables"

# Query for recent messages
duckdb mqtt_logger/data/mqtt_logs.db "SELECT * FROM water_level ORDER BY timestamp DESC LIMIT 10"
```

### Uploader Database Lock Issues

**Error: "Database is locked"**

This usually means both the MQTT Logger and Uploader are trying to write to the database:

- Ensure the uploader mounts the database as **read-only** (`:ro`)
- Verify only one process is writing to the database (the MQTT Logger)
- Check Docker volume mount: should be `/path/to/mqtt_logs.db:/data/tree.duckdb:ro`

### S3 Access Denied

- Verify AWS credentials are correct
- Check IAM policy is attached to the user
- Ensure bucket name in environment matches CDK output

### Data Not Updating

- Check MQTT Logger is running and receiving messages
- Check uploader is running on schedule
- Verify DuckDB file path is correct and readable
- Check Docker volume mount is working: `docker run -v /path:/data alpine ls -la /data`
- Verify the database has recent data

### Site Not Loading Data

- Verify `dataUrl` in `site/src/config.js` points to correct S3 URL
- Check browser console for CORS errors
- Ensure S3 bucket has public read access and CORS configured
- Test the S3 URL directly: `curl https://treelemetry-sbma44-water-data.s3.amazonaws.com/water-level.json`

### GitHub Pages Not Updating

- Verify `/docs` directory is committed and pushed
- Check GitHub Pages settings are correct
- GitHub Pages can take a few minutes to deploy
- Check the Pages build status in repository settings

### High SD Card Wear (Raspberry Pi)

If running MQTT Logger on Raspberry Pi with SD card:

- Increase `DB_BATCH_SIZE` (e.g., 5000)
- Increase `DB_FLUSH_INTERVAL` (e.g., 300 seconds)
- See [`mqtt_logger/SD_CARD_OPTIMIZATION.md`](mqtt_logger/SD_CARD_OPTIMIZATION.md) for detailed strategies

