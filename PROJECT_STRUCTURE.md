# Project Structure

Complete overview of the Treelemetry project structure.

```
treelemetry/
├── .github/
│   └── workflows/
│       └── deploy.yml          # GitHub Actions workflow for auto-deployment
│
├── docs/                        # Built static site (GitHub Pages)
│   ├── .gitkeep
│   └── index.html              # Placeholder until first build
│
├── infrastructure/              # AWS CDK infrastructure (IAM credentials)
│   ├── app.py                  # CDK app entry point
│   ├── cdk.json                # CDK configuration
│   ├── pyproject.toml          # Python dependencies (uv)
│   ├── README.md               # Infrastructure documentation
│   └── infrastructure/
│       ├── __init__.py
│       └── stack.py            # CDK stack definition
│
├── mqtt_logger/                 # MQTT message logger (Dockerized)
│   ├── Dockerfile              # Docker container definition
│   ├── docker-entrypoint.sh    # Container entry point
│   ├── main.py                 # Application entry point
│   ├── pyproject.toml          # Python dependencies (uv)
│   ├── mqtt-logger.service     # systemd service file
│   ├── README.md               # MQTT Logger documentation
│   ├── QUICKSTART.md           # Quick start guide
│   ├── DOCKER.md               # Docker deployment guide
│   ├── config/
│   │   └── mqtt_logger.example.toml  # Configuration template
│   ├── src/
│   │   └── mqtt_logger/
│   │       ├── app.py          # Main application
│   │       ├── config.py       # Configuration management
│   │       ├── mqtt_client.py  # MQTT client implementation
│   │       ├── storage.py      # DuckDB storage layer
│   │       └── alerting.py     # Email alerting for disk space
│   └── tests/                  # Comprehensive test suite
│
├── site/                        # Vite static site
│   ├── index.html              # Main HTML template
│   ├── package.json            # Node dependencies
│   ├── vite.config.js          # Vite configuration
│   ├── README.md               # Site documentation
│   └── src/
│       ├── main.js             # Application logic and Chart.js setup
│       ├── config.js           # Site configuration
│       └── style.css           # Styling with CSS custom properties
│
├── uploader/                    # Python uploader (Dockerized)
│   ├── Dockerfile              # Docker container definition
│   ├── pyproject.toml          # Python dependencies (uv)
│   ├── env.example             # Environment variable template
│   ├── run-docker.sh           # Docker run script
│   ├── sample_data.py          # Test data generator
│   ├── README.md               # Uploader documentation
│   └── src/
│       └── uploader.py         # Main uploader script
│
├── .gitattributes              # Git line ending configuration
├── .gitignore                  # Git ignore patterns
├── docker-compose.yml          # Docker Compose for easy deployment
├── DEPLOYMENT.md               # Complete deployment guide
├── LICENSE                     # MIT License
├── PROJECT_STRUCTURE.md        # This file
├── QUICKSTART.md               # Quick start guide
└── README.md                   # Main project documentation
```

## Component Descriptions

### MQTT Logger (`mqtt_logger/`)

Production-ready MQTT message logger that:
- Subscribes to MQTT topics with wildcard support
- Stores messages in DuckDB with batched writes
- Runs as systemd service or Docker container
- Features automatic reconnection and graceful shutdown
- Optional email alerting for disk space monitoring
- Optimized for Raspberry Pi / SD card longevity

**Tech Stack:** Python, paho-mqtt, DuckDB, Docker, systemd

### Infrastructure (`infrastructure/`)

AWS CDK application that provisions:
- S3 bucket with public read access and CORS
- IAM user with minimal permissions
- Access keys for the uploader

**Tech Stack:** Python, AWS CDK, boto3

### Uploader (`uploader/`)

Dockerized Python script that:
- Queries DuckDB for recent measurements
- Performs statistical aggregation (1m, 5m, 1h intervals)
- Analyzes consumption segments with linear regression
- Formats data as gzipped JSON
- Uploads to S3 with public access

**Tech Stack:** Python, DuckDB, boto3, pandas, scikit-learn, Docker

### Static Site (`site/`)

Modern, responsive visualization dashboard that:
- Fetches JSON data from S3
- Displays real-time water level charts with multiple time scales
- Shows consumption rate analysis and predictions
- Auto-refreshes every 30 seconds
- Responsive design with Chart.js

**Tech Stack:** Vite, Chart.js, date-fns, Vanilla JavaScript, CSS

### Deployment

The project uses a hybrid deployment strategy:

1. **MQTT Logger:** Docker or systemd → Runs on-premise (captures sensor data)
2. **Infrastructure:** AWS CDK → AWS (S3 + IAM credentials)
3. **Uploader:** Docker → Runs on-premise as daemon (uploads every 30s)
4. **Static Site:** Vite build → `docs/` → GitHub Pages

## Data Flow

```
IoT Sensors (ESP8266, Yolink, etc.)
    ↓ (MQTT messages)
MQTT Broker (Mosquitto on Raspberry Pi)
    ↓
MQTT Logger (Docker container on NAS)
    ↓
DuckDB File (local storage)
    ↓
Uploader (Docker container, daemon mode)
    ↓ (aggregated & analyzed data)
S3 Bucket (public gzipped JSON)
    ↓
Static Site (GitHub Pages)
    ↓
User's Browser (Chart.js visualization)
```

## Key Design Decisions

### Why DuckDB for MQTT Logger?

- Embedded database, no separate server needed
- Columnar storage, excellent compression
- Fast analytical queries for time-series data
- ACID transactions with write-ahead log
- Perfect for edge/IoT deployments

### Why Batched Writes?

- Extends SD card lifespan (10+ years vs 6-12 months)
- Reduces write amplification on flash storage
- Trade-off: potential data loss on unexpected shutdown
- Configurable based on storage type (SD vs SSD)

### Why uv for Python?

- Fast, modern Python package manager
- Replaces pip, pip-tools, virtualenv, and poetry
- Lockfile support for reproducible builds
- Native support for pyproject.toml

### Why Vite for the Site?

- Lightning-fast dev server and builds
- Native ES modules support
- Simple configuration
- Perfect for static sites

### Why Chart.js?

- Modern, actively maintained
- Simpler API than D3.js
- Built-in responsive design
- Good TypeScript support
- Excellent documentation

### Why GitHub Pages from `/docs`?

- Simple deployment (just commit and push)
- No separate deployment step needed
- Works well with monorepo structure
- Source and deployment in one branch

### Why Docker for Logger and Uploader?

- Isolated environment
- Easy deployment across different systems
- Consistent runtime
- Simple dependency management
- Can run as systemd service or container

## Development Workflow

### Initial Setup

1. Deploy infrastructure (`infrastructure/`) - creates S3 bucket and IAM credentials
2. Set up MQTT logger (`mqtt_logger/`) - captures sensor data to DuckDB
3. Build and test uploader (`uploader/`) - uploads aggregated data to S3
4. Configure site with S3 URL (`site/`) - visualization dashboard
5. Build site to `docs/`
6. Push to GitHub
7. Enable GitHub Pages

### Making Changes

**To the MQTT logger:**
```bash
cd mqtt_logger
# Edit src/mqtt_logger/*.py
uv run pytest  # Run tests
docker build -t mqtt-logger .
docker run -e MQTT_BROKER=localhost -e TOPICS="test/#:test:Test" mqtt-logger
```

**To the uploader:**
```bash
cd uploader
# Edit src/uploader.py
docker build -t treelemetry-uploader .
docker run --env-file .env -v /path/to/tree.duckdb:/data/tree.duckdb:ro treelemetry-uploader
```

**To the site:**
```bash
cd site
# Edit src/main.js or src/style.css
npm run dev  # Live preview
npm run build  # Build to ../docs/
git add ../docs && git commit && git push  # Deploy
```

**To the infrastructure:**
```bash
cd infrastructure
# Edit infrastructure/stack.py
npx aws-cdk diff  # Preview changes
npx aws-cdk deploy  # Apply changes
```

## Environment Variables

### MQTT Logger

- `MQTT_BROKER`: MQTT broker hostname or IP
- `MQTT_PORT`: MQTT broker port (default: 1883)
- `MQTT_USERNAME`: Optional MQTT authentication username
- `MQTT_PASSWORD`: Optional MQTT authentication password
- `TOPICS`: Topic patterns to subscribe (format: `pattern:table:description`)
- `DB_PATH`: Path to DuckDB database file
- `DB_BATCH_SIZE`: Messages to batch before writing
- `DB_FLUSH_INTERVAL`: Seconds between forced flushes
- `ALERT_EMAIL_TO`: Email address for disk space alerts (optional)
- `ALERT_DB_SIZE_MB`: Alert threshold for database size (optional)
- `ALERT_FREE_SPACE_MB`: Alert threshold for free disk space (optional)

### Uploader

- `DUCKDB_PATH`: Path to DuckDB file
- `S3_BUCKET`: S3 bucket name
- `S3_KEY`: S3 object key
- `AWS_ACCESS_KEY_ID`: AWS credentials
- `AWS_SECRET_ACCESS_KEY`: AWS credentials
- `MINUTES_OF_DATA`: Historical data window (default: 10)
- `REPLAY_DELAY_SECONDS`: Visualization replay delay (default: 300)
- `UPLOAD_INTERVAL_SECONDS`: Upload frequency (default: 30)

### Infrastructure

- `CDK_DEFAULT_ACCOUNT`: AWS account ID
- `CDK_DEFAULT_REGION`: AWS region

## Testing

### Test MQTT Logger

```bash
cd mqtt_logger
uv sync
uv run pytest  # Run test suite
uv run pytest --cov=src --cov-report=html  # With coverage
```

### Test with Sample Data

```bash
# Generate sample data
cd uploader
uv sync
uv run python sample_data.py ../tree.duckdb 1

# Test uploader locally
export DUCKDB_PATH=../tree.duckdb
uv run python src/uploader.py

# Test site locally
cd ../site
npm run dev
```

## Monitoring

### Check MQTT Logger

```bash
# Docker logs
docker logs mqtt-logger -f

# Systemd logs
sudo journalctl -u mqtt-logger -f

# Query logged data
duckdb data/mqtt_logs.db "SELECT COUNT(*) FROM water_level"
```

### Check Uploader

```bash
# Docker logs
docker logs treelemetry-uploader

# Systemd logs (if using systemd)
sudo journalctl -u treelemetry-uploader.service -f
```

### Verify S3 Upload

```bash
curl https://treelemetry-sbma44-water-data.s3.amazonaws.com/water-level.json
```

### Check GitHub Pages

Visit: https://sbma44.github.io/treelemetry

## Troubleshooting

See [DEPLOYMENT.md](DEPLOYMENT.md#troubleshooting) for common issues and solutions.

