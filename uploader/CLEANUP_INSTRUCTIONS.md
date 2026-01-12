# Immediate Cleanup Instructions

Your mqtt-logger is failing because the `treelemetry-uploader` container has consumed 1.8TB of disk space with temporary database files. Here's how to fix it immediately:

## Step 1: Stop and Remove the Uploader Container

```bash
# This will immediately free up the 1.8TB
docker stop treelemetry-uploader
docker rm treelemetry-uploader
```

## Step 2: Verify Space is Freed

```bash
docker system df
# The "Containers" line should now show much less space used
```

## Step 3: Verify mqtt-logger Can Write Again

```bash
docker logs xmas-mqtt-logger
# Should no longer show "could not write to disk" errors
```

## Step 4: Rebuild and Restart the Uploader (with fix)

```bash
cd uploader/

# Rebuild with the updated code
docker build -t treelemetry-uploader .

# Update run-docker.sh with your actual paths and credentials, then:
./run-docker.sh
```

## Step 5: Monitor to Ensure Fix Works

```bash
# Check that temp files aren't accumulating
docker exec treelemetry-uploader find /tmp -name "*.duckdb" 2>/dev/null

# Should show 0 or 1 file at most (only during active queries)
# If you see multiple files accumulating, there's still an issue
```

## What Was Fixed

The uploader code now uses Python context managers (`with` statements) to ensure temporary database copies are immediately deleted after each query, rather than relying on unreliable `atexit` handlers.

See `BUGFIX.md` for technical details.

## Prevention

The updated `run-docker.sh` now mounts `/tmp` to the host filesystem. This means:
- Even if cleanup fails, temp files go to your NAS storage (not container layer)
- You can easily monitor and clean up temp files
- Docker's overlay filesystem doesn't get filled up

## Emergency Recovery

If this happens again:

```bash
# Quick check which container is the culprit
docker ps -s

# See per-container breakdown
docker system df

# Clean up stopped containers
docker system prune -f
```


