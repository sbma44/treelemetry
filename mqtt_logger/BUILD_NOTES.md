# Build Notes & Troubleshooting

## Fixed Issues

### README.md Required for Build

**Issue:** Docker build fails with:
```
OSError: Readme file does not exist: README.md
```

**Cause:** The `pyproject.toml` file specifies `readme = "README.md"` and the hatchling build backend requires this file to be present during the build process.

**Solution:** `README.md` is now explicitly copied in the Dockerfile before `uv sync` runs, and `.dockerignore` has been updated to allow it while excluding other documentation files.

## Build Process

### Files Copied to Image

Essential files that MUST be in the image:
- `pyproject.toml` - Project metadata
- `uv.lock` - Dependency lock file
- `README.md` - **Required by build system**
- `src/` - Application code
- `main.py` - Entry point
- `docker-entrypoint.sh` - Startup script

### Files Excluded from Image

Excluded via `.dockerignore`:
- Other `.md` files (DOCKER.md, ALERTING.md, etc.) - Not needed at runtime
- Tests (`tests/`) - Not needed in production
- Development files (`.venv/`, `__pycache__/`, etc.)
- Data directories that will be mounted as volumes

## Startup Email Notification

### Feature
When `ALERT_EMAIL_TO` is configured, the container sends a startup success email containing:
- Container hostname
- Start timestamp
- MQTT broker configuration
- Database path
- Configured topics
- Batch and flush settings

### Example Email

```
Subject: MQTT Logger Started Successfully

MQTT Logger has started successfully!

Container: mqtt-logger
Start Time: 2024-12-02 15:30:45 EST

MQTT Configuration:
  Broker: 192.168.1.2:1883
  Client ID: (auto-generated)
  QoS: 1
  Username: (none)

Database Configuration:
  Path: /app/data/mqtt_logs.db
  Batch Size: 100 messages          ← Shows ACTUAL value after env override!
  Flush Interval: 30 seconds         ← Shows ACTUAL value after env override!

Topics:
  • xmas/tree/water/raw → water_level (Tree water level)

Logging:
  Level: INFO
  File: (stdout/journal only)

Email Alerts:
  Email: you@example.com
  DB Size Threshold: (disabled) MB
  Free Space Threshold: (disabled) MB
  Cooldown: 24 hours

This notification confirms that MQTT Logger started successfully with the
configuration values shown above (including any environment variable overrides).
```

**Important:** The email now shows the actual configuration values the application is using, including any environment variable overrides!

### Testing Startup Email

```bash
# Build with SMTP
SMTP_SERVER=smtp.gmail.com \
SMTP_FROM=you@gmail.com \
SMTP_TO=you@gmail.com \
SMTP_PASSWORD=app-password \
./build-docker.sh

# Run with email alerts and logs mounted
docker run -d \
  --name test-mqtt-logger \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  -e MQTT_BROKER=test.mosquitto.org \
  -e TOPICS="test/#:test:Test" \
  -e ALERT_EMAIL_TO=you@example.com \
  mqtt-logger

# Check logs for email send confirmation
docker logs test-mqtt-logger | grep -i "startup notification"

# Check msmtp log for details
cat logs/msmtp.log
```

**Note:** The startup email uses `msmtp` directly instead of the `mail` command for reliability.

## Common Build Issues

### Issue: Build hangs or is very slow

**Cause:** Downloading DuckDB wheel (19.5 MB)

**Solution:** This is normal. DuckDB is a large dependency. Subsequent builds will be faster due to Docker layer caching.

### Issue: Permission denied errors

**Cause:** Docker doesn't have permission to read project files

**Solution:**
```bash
# Ensure files are readable
chmod -R +r .

# Or build with sudo (not recommended)
sudo docker build -t mqtt-logger .
```

### Issue: Network timeout during build

**Cause:** Cannot reach package repositories

**Solution:**
```bash
# Check Docker network
docker network ls

# Try with different DNS
docker build --network=host -t mqtt-logger .

# Or configure Docker daemon to use different DNS
```

### Issue: "no space left on device"

**Cause:** Docker ran out of disk space

**Solution:**
```bash
# Clean up Docker
docker system prune -a

# Check disk space
df -h

# Remove unused images
docker images | grep none | awk '{print $3}' | xargs docker rmi
```

## Build Optimization

### Reducing Build Time

Use Docker layer caching effectively:

```bash
# Good: Dependencies change less often than code
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev
COPY src ./src
COPY main.py ./

# Bad: Would invalidate cache on any code change
COPY . .
RUN uv sync --frozen --no-dev
```

### Reducing Image Size

Current optimizations:
- Uses `slim` variant of base image
- Multi-stage SMTP config (only creates msmtprc if needed)
- Cleans up apt cache after package install
- Excludes tests and documentation via `.dockerignore`

Further optimization possible:
- Use `alpine` base (would require compilation)
- Multi-stage build to separate build and runtime dependencies

### Build Without Cache

Force fresh build:
```bash
docker build --no-cache -t mqtt-logger .
```

## Debugging Build Issues

### View Build Logs

```bash
# Build with more verbose output
docker build --progress=plain -t mqtt-logger .
```

### Inspect Failed Build

```bash
# If build fails at step N, inspect the last successful layer
docker run -it --rm <last-successful-layer-id> bash

# Example: Manually run the failing command
docker run -it --rm 185261be0cb8 bash
cd /app
uv sync --frozen --no-dev
```

### Test Build Components Individually

```bash
# Test SMTP config generation
docker build --target <layer> -t test .

# Test uv sync in isolation
docker run -it --rm ghcr.io/astral-sh/uv:python3.12-bookworm-slim bash
apt-get update && apt-get install -y git
# ... test commands
```

## Verifying Successful Build

### Check Image Size

```bash
docker images mqtt-logger
# Should be around 200-300 MB
```

### Check Image Layers

```bash
docker history mqtt-logger
```

### Test Run

```bash
# Quick test without volumes
docker run --rm mqtt-logger echo "Build successful"

# Test entrypoint
docker run --rm \
  -e MQTT_BROKER=test.mosquitto.org \
  -e TOPICS="test/#:test:Test" \
  mqtt-logger \
  sh -c "ls -la /app && cat /app/config/mqtt_logger.toml"
```

### Verify SMTP Configuration

```bash
# If built with SMTP args
docker run --rm mqtt-logger cat /root/.msmtprc

# Should show msmtp config with your settings
```

## Production Build Checklist

Before deploying:

- [ ] Build completed without errors
- [ ] Image size is reasonable (< 500 MB)
- [ ] SMTP configuration is correct (if using email alerts)
- [ ] Test run produces valid config
- [ ] Entrypoint script is executable
- [ ] All required files are present in image
- [ ] No sensitive data hardcoded in image

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Build Docker Image

on:
  push:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Build image
        run: |
          docker build \
            --build-arg SMTP_SERVER=${{ secrets.SMTP_SERVER }} \
            --build-arg SMTP_FROM=${{ secrets.SMTP_FROM }} \
            --build-arg SMTP_TO=${{ secrets.SMTP_TO }} \
            --build-arg SMTP_PASSWORD=${{ secrets.SMTP_PASSWORD }} \
            -t mqtt-logger:${{ github.sha }} \
            .
      
      - name: Test image
        run: |
          docker run --rm mqtt-logger:${{ github.sha }} --version
```

## Summary

The build process is now robust and includes:
1. ✅ All required files copied in correct order
2. ✅ Efficient layer caching
3. ✅ Startup success notifications
4. ✅ Comprehensive error handling
5. ✅ Production-ready configuration

If you encounter issues not covered here, check the logs with `docker build --progress=plain` and inspect the failing layer.

