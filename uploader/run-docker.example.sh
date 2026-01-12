#!/bin/bash
# Run treelemetry uploader as a daemon
#
# SETUP:
#   1. Copy this file: cp run-docker.example.sh run-docker.sh
#   2. Edit run-docker.sh with your actual values
#   3. Run: ./run-docker.sh
#
# The database is mounted :ro (read-only) to prevent lock conflicts
# Note: /tmp is mounted to prevent temp file accumulation in container layer

# Configuration - EDIT THESE VALUES
AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-YOUR_AWS_ACCESS_KEY_ID}"
AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-YOUR_AWS_SECRET_ACCESS_KEY}"
S3_BUCKET="${S3_BUCKET:-YOUR_S3_BUCKET_NAME}"
S3_KEY="${S3_KEY:-water-level.json}"
DUCKDB_PATH="${DUCKDB_PATH:-/path/to/your/mqtt_logs.db}"
UPLOAD_INTERVAL_SECONDS="${UPLOAD_INTERVAL_SECONDS:-30}"

docker run -d \
  --name treelemetry-uploader \
  --restart unless-stopped \
  -e AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID" \
  -e AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY" \
  -e S3_BUCKET="$S3_BUCKET" \
  -e S3_KEY="$S3_KEY" \
  -e UPLOAD_INTERVAL_SECONDS="$UPLOAD_INTERVAL_SECONDS" \
  -v "$DUCKDB_PATH":/data/tree.duckdb:ro \
  -v "$(pwd)/tmp":/tmp \
  treelemetry-uploader

