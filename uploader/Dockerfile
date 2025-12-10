FROM python:3.11-slim

# Install uv
RUN pip install uv

# Set working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml .
COPY src/ src/

# Install dependencies using uv
RUN uv pip install --system -e .

# Create data directory for mounting DuckDB
RUN mkdir -p /data

# Environment variable defaults
# These can be overridden at runtime with docker run -e
ENV DUCKDB_PATH=/data/tree.duckdb \
    MINUTES_OF_DATA=10 \
    S3_BUCKET=treelemetry-sbma44-water-data \
    S3_KEY=water-level.json \
    REPLAY_DELAY_SECONDS=300 \
    UPLOAD_INTERVAL_SECONDS=30

# AWS credentials must be provided at runtime (no defaults for security)
# Pass with: docker run -e AWS_ACCESS_KEY_ID=xxx -e AWS_SECRET_ACCESS_KEY=yyy

# Run the uploader as a long-running daemon
CMD ["python", "src/uploader.py"]


