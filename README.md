# Treelemetry 🎄💧

A sophisticated monitoring system for tracking Christmas tree water levels with unnecessary precision.

## Project Overview

This project monitors and visualizes the water level of a Christmas tree through three main components:

1. **Data Sleigh** - Unified MQTT logger, YoLink sensor integration, and S3 uploader with season-aware behavior
2. **Infrastructure** - AWS CDK scripts that provision S3 bucket and IAM credentials
3. **Static Site** - Vite-powered visualization dashboard served via GitHub Pages

## Architecture

```
IoT Sensors (ESP8266, YoLink, etc.)
    ↓ (MQTT messages)
┌─────────────────────────────────────┐
│           Data Sleigh               │
│  ┌─────────────┐  ┌──────────────┐  │
│  │ Local MQTT  │  │ YoLink Cloud │  │
│  └──────┬──────┘  └──────┬───────┘  │
│         └────────┬───────┘          │
│                  ↓                  │
│         DuckDB (normalized)         │
│                  ↓                  │
│         [Season Check]              │
│              ↓    ↓                 │
│        IN-SEASON  OFF-SEASON        │
│           ↓           ↓             │
│      Aggregate    Monthly           │
│      & Upload     Backup            │
└──────────┬────────────┬─────────────┘
           ↓            ↓
    S3 (JSON)     S3 (backups/)
           ↓
    GitHub Pages (static site)
           ↓
    User's Browser (Chart.js)
```

## Setup

### Prerequisites

- Python 3.11-3.13 with [uv](https://github.com/astral-sh/uv) installed
- Node.js 18+ with npm (for CDK CLI via `npx` and Vite)
- Docker
- AWS CLI configured with appropriate permissions
- MQTT broker (e.g., Mosquitto) for IoT sensor data

### 1. Data Sleigh Setup

Data Sleigh is the unified data collection and upload service. See [`data_sleigh/README.md`](data_sleigh/README.md) for complete documentation.

**Quick Start with Docker:**

```bash
cd data_sleigh

# Copy and edit the example configuration
cp run-docker-data-sleigh.example.sh run-docker-data-sleigh.sh
# Edit run-docker-data-sleigh.sh with your settings

# Build and run
docker build -t data-sleigh .
./run-docker-data-sleigh.sh
```

**Key Features:**
- 📡 Dual MQTT support (local broker + YoLink cloud)
- 🔄 Season-aware behavior (automatic in-season/off-season modes)
- 💾 Efficient DuckDB storage with normalized YoLink schema
- ☁️ Gzip-compressed JSON uploads to S3
- 📦 Automatic monthly backups during off-season
- 📧 Email alerts for disk space monitoring

### 2. Infrastructure Setup

Deploy the CDK stack to create S3 bucket and IAM credentials:

```bash
cd infrastructure
uv sync
npx aws-cdk bootstrap  # First time only
npx aws-cdk deploy
```

After deployment, the stack outputs will include the IAM credentials needed for Data Sleigh.

### 3. Static Site Development

```bash
cd site
npm install
npm run dev    # Development server
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
- **Season info** (start date, end date, active status)
- **Raw measurements** (last 10 minutes)
- **Aggregated data** (1m, 5m, 1h intervals)
- **Consumption analysis** (detected segments, slopes, predictions)
- **Statistics** (min, max, avg, stddev)

All data is gzip-compressed for efficient transfer.

**Sample structure:**
```json
{
  "generated_at": "2025-12-05T12:00:00Z",
  "season": {
    "start": "2025-12-01",
    "end": "2026-01-15",
    "is_active": true
  },
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
├── data_sleigh/       # Unified MQTT logger + S3 uploader
│   ├── Dockerfile
│   ├── main.py
│   ├── config/        # Configuration templates
│   ├── src/           # Implementation
│   ├── tests/         # Test suite
│   └── tools/         # CLI utilities
├── infrastructure/    # AWS CDK for S3 & IAM
│   ├── app.py
│   ├── cdk.json
│   └── infrastructure/
├── site/              # Vite static site
│   ├── index.html
│   ├── package.json
│   └── src/
├── docs/              # Built site (GitHub Pages)
├── mqtt_logger/       # Legacy (replaced by data_sleigh)
└── uploader/          # Legacy (replaced by data_sleigh)
```

See [`PROJECT_STRUCTURE.md`](PROJECT_STRUCTURE.md) for complete details.

### Running Tests

```bash
# Data Sleigh tests
cd data_sleigh
uv sync --all-extras
uv run pytest

# With coverage
uv run pytest --cov=src --cov-report=html
```

### Makefile Targets

```bash
make help              # Show available targets
make install           # Install all dependencies
make build-docker      # Build Docker images
make test              # Run tests
make dev-site          # Start site dev server
make status            # Check component status
```

## Migration Notes

Data Sleigh consolidates the previous `mqtt_logger` and `uploader` components:

**Benefits:**
- ✅ Eliminates DuckDB locking issues (single process)
- ✅ Simplified deployment (one container vs two)
- ✅ Season-aware behavior built-in
- ✅ Improved YoLink schema (normalized columns)
- ✅ Monthly backups during off-season

The legacy `mqtt_logger/` and `uploader/` directories are preserved for reference but are no longer actively maintained.

## License

MIT
