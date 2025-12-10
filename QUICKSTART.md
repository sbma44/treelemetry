# Quick Start Guide

Get Treelemetry up and running in minutes!

## Overview

Treelemetry consists of four components:

1. **MQTT Logger** - Captures sensor data (for production use)
2. **Infrastructure** - AWS resources (S3 + IAM)
3. **Uploader** - Aggregates and uploads data
4. **Static Site** - Visualization dashboard

This guide shows how to deploy with **sample data**. For production with real sensors, see [`mqtt_logger/QUICKSTART.md`](mqtt_logger/QUICKSTART.md) first.

## 1. Generate Sample Data (Optional)

If you don't have a real DuckDB file from the MQTT Logger yet, create sample data:

```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Generate sample data
cd uploader
uv sync
uv run python sample_data.py ../tree.duckdb 1
cd ..
```

This creates a `tree.duckdb` file with 1 day of sample measurements.

## 2. Deploy Infrastructure

```bash
cd infrastructure
uv sync
npx aws-cdk deploy
```

**Important:** Save the output values! You'll need them for the next steps.

Note: `npx` will download and run the CDK CLI without requiring a global install.

## 3. Test the Uploader Locally

```bash
cd uploader
cp env.example .env
# Edit .env and set:
#   - AWS_ACCESS_KEY_ID (from step 2)
#   - AWS_SECRET_ACCESS_KEY (from step 2)
#   - DUCKDB_PATH=/Users/tomlee/code/python/treelemetry/mqtt_logs.db
# Bucket name is already set to: treelemetry-sbma44-water-data

uv run python src/uploader.py
```

The script will automatically load settings from `.env`.

## 4. Build the Site

The site is already configured to use the fixed bucket name.

Build the site:

```bash
cd site
npm install
npm run build
```

## 5. Deploy to GitHub

```bash
git add .
git commit -m "Initial Treelemetry setup"
git push origin main
```

Enable GitHub Pages in your repository settings:
- Settings → Pages
- Source: Deploy from a branch
- Branch: `main`, Folder: `/docs`

## 6. Run the Uploader in Docker

```bash
cd uploader
docker build -t treelemetry-uploader .
docker run -d \
  --name treelemetry-uploader \
  --restart unless-stopped \
  -e AWS_ACCESS_KEY_ID=xxx \
  -e AWS_SECRET_ACCESS_KEY=yyy \
  -v /Users/tomlee/code/python/treelemetry/mqtt_logs.db:/data/tree.duckdb:ro \
  treelemetry-uploader
```

Replace `xxx` and `yyy` with your actual AWS credentials from step 2.

The container runs as a daemon, uploading data every 30 seconds automatically. No cron or systemd timers needed!

View logs:
```bash
docker logs -f treelemetry-uploader
```

Stop the uploader:
```bash
docker stop treelemetry-uploader
```

## 7. Verify Everything Works

Check the uploader logs:
```bash
docker logs treelemetry-uploader
```

You should see:
```
🎄 Treelemetry Uploader
✓ Database file found
✓ Starting upload daemon...
[2025-12-10 12:00:00] Upload #1
  Retrieved 200 raw measurements
  Aggregated: 1m=60 pts, 5m=288 pts, 1h=24 pts
  ✓ Upload complete in 0.8s
```

Verify the S3 file:
```bash
curl https://treelemetry-sbma44-water-data.s3.amazonaws.com/water-level.json
```

## Done! 🎄

Your Christmas tree water level is now being monitored with unnecessary precision!

## Production Deployment with Real Sensors

For production use with real IoT sensors:

1. **Set up MQTT Logger first** - See [`mqtt_logger/QUICKSTART.md`](mqtt_logger/QUICKSTART.md)
2. Wait for sensor data to accumulate in the database
3. Configure the uploader to read from the MQTT Logger's database:
   ```bash
   DUCKDB_PATH=/path/to/mqtt_logger/data/mqtt_logs.db
   ```
4. Deploy as shown in steps 2-6 above

The MQTT Logger creates and maintains the DuckDB database that the uploader reads from.

For detailed instructions, see [DEPLOYMENT.md](DEPLOYMENT.md).

