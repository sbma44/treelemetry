# Bug Fix: Temporary Database File Accumulation

## Problem

The uploader was accumulating temporary database copies in `/tmp` within the Docker container, eventually consuming 1.8TB of disk space and preventing other containers (like mqtt-logger) from writing to disk.

### Root Cause

When the uploader couldn't acquire a file lock on the mounted DuckDB database (common with NAS/network mounts), it would copy the entire database to a temporary file in `/tmp`. The cleanup relied on `atexit` handlers, which don't run reliably in long-running daemon processes:

```python
# OLD CODE - unreliable cleanup
import atexit
atexit.register(lambda: Path(tmp_path).unlink(missing_ok=True))
return conn  # Connection stays open, temp file persists
```

Problems with this approach:
1. `atexit` handlers only run on normal process exit
2. Long-running daemons may never exit normally
3. If connections weren't closed properly, temp files would persist
4. Over 13 days of 30-second intervals = ~37,000 database copies!

## Solution

Converted `get_db_connection()` from a regular function to a **context manager** that guarantees immediate cleanup:

```python
@contextmanager
def get_db_connection(db_path: Path):
    conn = None
    tmp_path = None

    try:
        # Try to connect...
        yield conn
    finally:
        # ALWAYS clean up, even on exceptions
        if conn:
            conn.close()
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)
```

All query functions were updated to use the context manager:

```python
# NEW CODE - guaranteed cleanup
with get_db_connection(db_path) as conn:
    result = conn.execute(query).fetchall()
    # Connection closed and temp files deleted automatically
```

## Changes Made

### Modified Functions

1. **`get_db_connection()`** - Converted to context manager with `@contextmanager` decorator
2. **`query_water_levels()`** - Updated to use `with` statement
3. **`query_aggregated_data()`** - Updated to use `with` statement
4. **`query_yolink_aggregated_data()`** - Updated to use `with` statement
5. **`analyze_water_level_segments()`** - Updated to use `with` statement

### Benefits

- ✅ Temp files are deleted immediately after each query
- ✅ Works even if exceptions occur
- ✅ No reliance on process exit or garbage collection
- ✅ Pythonic and follows best practices
- ✅ No behavior changes for users of these functions

## Testing

To verify the fix works:

```bash
# Before: Check current temp file accumulation
docker exec treelemetry-uploader du -sh /tmp/*
docker exec treelemetry-uploader find /tmp -name "*.duckdb" | wc -l

# Stop and rebuild with the fix
docker stop treelemetry-uploader
docker rm treelemetry-uploader
# Rebuild and restart container

# After: Monitor that temp files are cleaned up
docker exec treelemetry-uploader watch -n 5 'ls -lh /tmp/*.duckdb 2>/dev/null | wc -l'
# Should show 0 or 1 at most (only during active query)
```

## Prevention

To prevent similar issues in the future:

1. **Always use context managers** for resources that need cleanup (files, connections, locks)
2. **Never rely on `atexit`** for cleanup in long-running daemons
3. **Monitor container disk usage**: `docker ps -s` and `docker system df`
4. **Mount `/tmp` to host storage** if working with large temporary files

## Related Files

- `uploader/src/uploader.py` - Main file with all fixes
- `uploader/Dockerfile` - Consider adding volume mount for `/tmp`
- `uploader/run-docker.sh` - Update to mount `/tmp` volume

## Credits

Fixed on 2025-12-24 by identifying 1.8TB container disk usage via `docker system df`.


