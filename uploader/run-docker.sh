#!/bin/bash
# Run treelemetry uploader as a daemon
# The database is mounted :ro (read-only) to prevent lock conflicts
docker run -d \
  --name treelemetry-uploader \
  --restart unless-stopped \
  -e AWS_ACCESS_KEY_ID=AWS_ACCESS_KEY_HERE \
  -e AWS_SECRET_ACCESS_KEY=AWS_SECRET_ACCESS_KEY_HERE \
  -e UPLOAD_INTERVAL_SECONDS=30 \
  -v $(pwd)/../path/to/duckdb/file/tree.duckdb:/data/tree.duckdb:ro \
  treelemetry-uploader