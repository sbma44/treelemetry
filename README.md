# Treelemetry 🎄💧

A sophisticated monitoring system for tracking Christmas tree water levels with unnecessary precision.

## Project Overview

This project monitors and visualizes the water level of a Christmas tree through four main components:

1. **MQTT Logger** - Captures MQTT messages from IoT sensors and stores them in DuckDB
2. **Uploader** - Queries DuckDB, aggregates data, and uploads to S3
3. **Infrastructure** - AWS CDK scripts that provision S3 bucket and IAM credentials
4. **Static Site** - Vite-powered visualization dashboard served via GitHub Pages

## Architecture

```
IoT Sensors (ESP8266, Yolink, etc.)
    ↓ (MQTT messages)
MQTT Broker (Mosquitto)
    ↓
MQTT Logger (Docker/systemd)
    ↓
DuckDB File (batched writes)
    ↓
Uploader (Docker daemon)
    ↓ (aggregated data)
S3 Bucket (gzipped JSON, public)
    ↓
GitHub Pages (static site)
    ↓
User's Browser (Chart.js visualizations)
```

## Setup

### Prerequisites

- Python 3.11+ with [uv](https://github.com/astral-sh/uv) installed
- Node.js 18+ with npm (for CDK CLI via `npx` and Vite)
- Docker
- AWS CLI configured with appropriate permissions
- MQTT broker (e.g., Mosquitto) for IoT sensor data

### 1. MQTT Logger Setup

The MQTT Logger captures sensor data and stores it in DuckDB. See [`mqtt_logger/README.md`](mqtt_logger/README.md) for complete documentation.

**Quick Start with Docker:**

```bash
cd mqtt_logger
docker build -t mqtt-logger .
docker run -d \
  --name mqtt-logger \
  --restart unless-stopped \
  -v $(pwd)/data:/app/data \
  -e MQTT_BROKER=mqtt.example.com \
  -e TOPICS="xmas/tree/water/raw:water_level:Water level readings" \
  mqtt-logger
```

**Or with systemd:** See [`mqtt_logger/QUICKSTART.md`](mqtt_logger/QUICKSTART.md)

### 2. Uploader Setup

The uploader runs as a long-running daemon that queries DuckDB and uploads to S3.

```bash
cd uploader
uv sync
```

Build and run the Docker container:

```bash
cd uploader
docker build -t treelemetry-uploader .
docker run -d \
  --name treelemetry-uploader \
  --restart unless-stopped \
  -e AWS_ACCESS_KEY_ID=xxx \
  -e AWS_SECRET_ACCESS_KEY=yyy \
  -v /path/to/mqtt_logs.db:/data/tree.duckdb:ro \
  treelemetry-uploader
```

The container runs continuously, uploading every 30 seconds.

### 3. Infrastructure Setup

Deploy the CDK stack to create IAM credentials:

```bash
cd infrastructure
uv sync
npx aws-cdk bootstrap  # First time only
npx aws-cdk deploy
```

After deployment, the stack outputs will include the IAM credentials needed for the uploader.

### 4. Static Site Development

```bash
cd site
npm install
npm run dev  # Development server
npm run build  # Production build to ../docs/
```

### GitHub Pages Deployment

The static site is built to the `docs/` directory and served via GitHub Pages:

1. Push changes to GitHub
2. Go to repository Settings → Pages
3. Set source to "Deploy from a branch"
4. Select `main` branch and `/docs` folder
5. Site will be available at: https://treelemetry.tomlee.space

## Data Format

The JSON file uploaded to S3 includes:
- **Raw measurements** (last 10 minutes)
- **Aggregated data** (1m, 5m, 1h intervals)
- **Consumption analysis** (detected segments, slopes, predictions)
- **Statistics** (min, max, avg, stddev)

All data is gzip-compressed for efficient transfer.

**Sample structure:**
```json
{
  "generated_at": "2025-12-05T12:00:00Z",
  "measurements": [...],
  "agg_1m": { "data": [...] },
  "agg_5m": { "data": [...] },
  "agg_1h": { "data": [...] },
  "analysis": {
    "segments": [...],
    "current_prediction": {
      "slope_mm_per_hr": 2.5,
      "time_to_50mm_hours": 8.5
    }
  }
}
```

## Development

### Project Structure

```
treelemetry/
├── mqtt_logger/       # MQTT message logger
│   ├── Dockerfile
│   ├── main.py
│   ├── config/       # Configuration templates
│   ├── src/          # Logger implementation
│   └── tests/        # Test suite
├── uploader/          # Data aggregation & S3 uploader
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── sample_data.py # Test data generator
│   └── src/
├── infrastructure/    # AWS CDK for S3 & IAM
│   ├── app.py
│   ├── cdk.json
│   └── infrastructure/
├── site/             # Vite static site
│   ├── index.html
│   ├── package.json
│   └── src/
└── docs/             # Built site (GitHub Pages)
```

See [`PROJECT_STRUCTURE.md`](PROJECT_STRUCTURE.md) for complete details.

## License

MIT

