# Treelemetry Uploader

Python script that queries water level data from DuckDB and uploads it to S3.

## Overview

The uploader is part of the Treelemetry pipeline:

```
MQTT Logger → DuckDB → Uploader → S3 → Static Site
```

In production, the **MQTT Logger** creates and maintains the DuckDB database that this uploader reads from. See [`../mqtt_logger/README.md`](../mqtt_logger/README.md) for setting up the data collection layer.

For testing without real sensors, you can use the sample data generator (see below).

## Setup

Install dependencies using `uv`:

```bash
uv sync
```

## Generating Test Data

For testing without the MQTT Logger, you can generate sample data:

```bash
uv run python sample_data.py ../test.duckdb 1
```

This creates a `test.duckdb` file with 1 day of sample measurements in the MQTT log format.

**Production use:** In production, point the uploader to the database created by the MQTT Logger:
```bash
DUCKDB_PATH=/path/to/mqtt_logger/data/mqtt_logs.db
```

## Local Development

Run locally (requires DuckDB file and AWS credentials).

### Option 1: Using .env file (Recommended)

```bash
# Create .env file from example
cp env.example .env

# Edit .env with your configuration
# Then run:
uv run python src/uploader.py
```

The script automatically loads variables from `.env` if it exists.

### Option 2: Using environment variables

```bash
export DUCKDB_PATH=/path/to/tree.duckdb
export S3_BUCKET=treelemetry-sbma44-water-data
export S3_KEY=water-level.json
export AWS_ACCESS_KEY_ID=your-access-key
export AWS_SECRET_ACCESS_KEY=your-secret-key

uv run python src/uploader.py
```

## Features

- **Long-running daemon**: Handles its own upload schedule
- **Gzip compression**: Reduces bandwidth by 70-85%
- **Automatic fallback**: Handles Docker volume mount lock issues
- **Graceful shutdown**: Responds to SIGTERM/SIGINT
- **Robust error handling**: Retries on transient failures
- **Quiet operation**: Only logs startup, first upload, and errors

## Docker Usage

Build the Docker image:

```bash
docker build -t treelemetry-uploader .
```

Run the container:

```bash
docker run \
  -e AWS_ACCESS_KEY_ID=xxx \
  -e AWS_SECRET_ACCESS_KEY=yyy \
  -e S3_BUCKET=your-bucket \
  -e S3_KEY=water-level.json \
  -v /path/to/tree.duckdb:/data/tree.duckdb:ro \
  treelemetry-uploader
```

### Error Handling

The uploader includes robust error handling:

- **Transient errors**: Logs error, waits for next interval, retries
- **Consecutive failures**: Exits after 10 consecutive failures (Docker/systemd will restart)
- **Graceful shutdown**: Responds to SIGTERM/SIGINT (Ctrl+C or `docker stop`)
- **Lock conflicts**: Automatically falls back to temporary copy if direct access fails

### Docker Volume Mount Issues

On macOS and some other systems, DuckDB's file locking doesn't work well across Docker volume mounts. If you see lock errors, the uploader automatically works around this by:

1. First trying direct read-only access
2. If that fails due to locking, copying the database to a temporary location inside the container
3. Reading from the temporary copy (slightly slower but reliable)

You may see a message: `"Note: Using temporary copy due to lock constraints"` - this is normal and expected.

Check container logs:

```bash
docker logs -f treelemetry-uploader
```

Look for:
- Upload count and success messages
- Error messages and retry attempts
- Statistics on measurements retrieved

## Environment Variables

- `DUCKDB_PATH`: Path to DuckDB file (default: `/data/tree.duckdb`)
- `S3_BUCKET`: S3 bucket name (required)
- `S3_KEY`: S3 object key (default: `water-level.json`)
- `AWS_ACCESS_KEY_ID`: AWS access key (required)
- `AWS_SECRET_ACCESS_KEY`: AWS secret key (required)
- `MINUTES_OF_DATA`: Minutes of historical data to query (default: `10`)
- `REPLAY_DELAY_SECONDS`: Delay for visualization replay (default: `300`)

## Database Schema

The script expects a table named `water_level` with the MQTT log format (created automatically by the MQTT Logger):

```sql
CREATE TABLE water_level (
    id INTEGER PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    topic VARCHAR NOT NULL,
    payload VARCHAR,
    qos INTEGER,
    retain BOOLEAN
);
```

The water level measurement is stored in the `payload` field as a string and is cast to DOUBLE during querying. The script filters for the topic `xmas/tree/water/raw`.

**Note:** This table is automatically created and populated by the MQTT Logger component. You don't need to create it manually unless you're using the sample data generator for testing.

