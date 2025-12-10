# SD Card Optimization Guide for Raspberry Pi

This guide explains how to minimize SD card wear when running MQTT Logger on a Raspberry Pi or other devices with SD card storage.

## Why This Matters

SD cards have limited write cycles (typically 10,000-100,000 writes per cell). Frequent small writes can significantly reduce SD card lifespan. This guide helps you configure the system to minimize writes while accepting some risk of data loss on unexpected shutdown.

## Quick Configuration

### Recommended Settings for SD Cards

Edit your `config/mqtt_logger.toml`:

```toml
[database]
path = "data/mqtt_logs.db"

# Large batch size = fewer writes
# Risk: Lose up to 5000 messages on crash
batch_size = 5000

# Long flush interval = less frequent writes
# Risk: Lose up to 5 minutes of data on crash
flush_interval = 300  # 5 minutes
```

### Trade-offs

| Setting | SD Card Friendly | Data Safety |
|---------|------------------|-------------|
| `batch_size = 100, flush_interval = 10` | ❌ More writes | ✅ Minimal data loss |
| `batch_size = 1000, flush_interval = 60` | ⚠️ Moderate writes | ⚠️ ~1 min data loss |
| `batch_size = 5000, flush_interval = 300` | ✅ Minimal writes | ❌ ~5 min data loss |

## Advanced Optimizations

### 1. Use tmpfs for Database (RAM Disk)

Store the entire database in RAM and periodically backup to SD card:

```toml
[database]
# Store database in RAM
path = "/tmp/mqtt_logs.db"
batch_size = 5000
flush_interval = 300
```

Then set up a cron job to backup periodically:

```bash
# Add to /etc/cron.hourly/backup-mqtt-db
#!/bin/bash
cp /tmp/mqtt_logs.db /opt/mqtt-logger/data/mqtt_logs_backup.db 2>/dev/null
```

**Pros:**
- No SD card writes during normal operation
- Very fast database operations
- Maximum SD card lifespan

**Cons:**
- All data lost on reboot/crash
- Requires sufficient RAM
- Need backup strategy

### 2. Mount Database Directory on tmpfs

Keep the main database on SD card but use RAM for temporary files:

```bash
# Add to /etc/fstab
tmpfs /opt/mqtt-logger/data/tmp tmpfs defaults,noatime,size=512M 0 0
```

Configure DuckDB to use this for temp files (this is already configured in the code).

### 3. Optimize System-Wide SD Card Settings

Add these to `/etc/fstab`:

```bash
# Reduce write frequency with noatime
/dev/mmcblk0p2 / ext4 defaults,noatime,nodiratime 0 1
```

Disable swap if not needed:

```bash
sudo dphys-swapfile swapoff
sudo dphys-swapfile uninstall
sudo systemctl disable dphys-swapfile
```

### 4. Log to RAM Disk

Configure logging to RAM instead of SD card:

```toml
[logging]
level = "INFO"
file = "/tmp/mqtt_logger.log"  # Use tmpfs
```

Or configure systemd to use only journal (already in RAM):

```toml
[logging]
level = "INFO"
# No file = journal only
```

### 5. Periodic Checkpoints

Instead of time-based flushing, flush only on significant events:

```toml
[database]
batch_size = 10000  # Very large batch
flush_interval = 86400  # 24 hours (effectively disabled)
```

Then manually trigger flushes via signal (future feature) or external script.

## Configuration Examples

### Minimal Writes (Aggressive)

**Best for:** Low-frequency sensors, non-critical data

```toml
[database]
path = "/tmp/mqtt_logs.db"  # RAM disk
batch_size = 10000
flush_interval = 3600  # 1 hour
```

**Data loss risk:** Up to 1 hour of data on crash

### Balanced (Recommended for SD Cards)

**Best for:** Most use cases on Raspberry Pi

```toml
[database]
path = "data/mqtt_logs.db"
batch_size = 5000
flush_interval = 300  # 5 minutes
```

**Data loss risk:** Up to 5 minutes of data on crash

### Conservative (Moderate Protection)

**Best for:** Important data that still needs SD card protection

```toml
[database]
path = "data/mqtt_logs.db"
batch_size = 1000
flush_interval = 60  # 1 minute
```

**Data loss risk:** Up to 1 minute of data on crash

## Monitoring SD Card Health

### Check Write Operations

```bash
# Install iotop to monitor writes
sudo apt install iotop
sudo iotop -o

# Check total writes
sudo smartctl -a /dev/mmcblk0
```

### Check Database Size Growth

```bash
# Monitor database size
watch -n 60 'ls -lh /opt/mqtt-logger/data/'

# Check DuckDB WAL file
ls -lh /opt/mqtt-logger/data/*.wal
```

## DuckDB Optimizations (Built-in)

The MQTT Logger automatically configures DuckDB with these SD-card-friendly settings:

1. **`wal_autocheckpoint='1GB'`** - Delays checkpoint operations
2. **`checkpoint_threshold='1GB'`** - Reduces checkpoint frequency

These settings keep more data in the Write-Ahead Log (WAL) file in memory before flushing to the main database file.

## Backup Strategy

Since we're prioritizing minimal writes over durability, implement a backup strategy:

### Daily Backup to Network Storage

```bash
#!/bin/bash
# /etc/cron.daily/backup-mqtt-db

DB_PATH="/opt/mqtt-logger/data/mqtt_logs.db"
BACKUP_PATH="/mnt/nas/mqtt_backups"
DATE=$(date +%Y%m%d)

# Stop service briefly for consistent backup
systemctl stop mqtt-logger
cp "$DB_PATH" "$BACKUP_PATH/mqtt_logs_${DATE}.db"
systemctl start mqtt-logger

# Keep only last 7 days
find "$BACKUP_PATH" -name "mqtt_logs_*.db" -mtime +7 -delete
```

### Export to External Database

Periodically export data to a more durable storage:

```python
# export_to_postgres.py
import duckdb
import psycopg2

# Read from DuckDB
conn = duckdb.connect('data/mqtt_logs.db')
data = conn.execute("SELECT * FROM sensors WHERE timestamp > NOW() - INTERVAL '1 day'").fetchall()

# Write to PostgreSQL
pg_conn = psycopg2.connect("host=server dbname=mqtt user=user password=pass")
# ... insert data
```

## Expected SD Card Lifespan

### Write Calculations

Assumptions:
- 100 MQTT messages/minute
- Average message size: 100 bytes
- SD card: 32GB, 10,000 write cycles per block

**With Default Settings (batch_size=100, flush_interval=10s):**
- ~6 flushes/minute
- ~8.64 million flushes/day
- Estimated lifespan: ~6-12 months

**With Optimized Settings (batch_size=5000, flush_interval=300s):**
- ~0.2 flushes/minute (once per 5 min)
- ~288 flushes/day
- Estimated lifespan: ~10+ years

## Monitoring and Alerts

Set up alerts for:

1. **Database size exceeding threshold**
2. **Flush failures** (check logs)
3. **Unusual disk write patterns**

```bash
# Check for errors in logs
journalctl -u mqtt-logger | grep -i error

# Monitor batch queue sizes (future feature)
# This would show if batches aren't being processed
```

## Troubleshooting

### Database Corruption

If the database becomes corrupted due to unexpected shutdown:

```bash
# Stop service
sudo systemctl stop mqtt-logger

# Check integrity
duckdb data/mqtt_logs.db "PRAGMA integrity_check;"

# Export data if readable
duckdb data/mqtt_logs.db "COPY sensors TO 'backup.csv' (FORMAT CSV, HEADER);"

# Recreate if necessary
rm data/mqtt_logs.db
sudo systemctl start mqtt-logger
```

### Out of Memory

If batch sizes are too large:

```bash
# Check memory usage
free -h

# Reduce batch_size in config
# Restart service
sudo systemctl restart mqtt-logger
```

## Summary

For Raspberry Pi with SD card storage, I recommend:

```toml
[database]
path = "data/mqtt_logs.db"
batch_size = 5000      # 50x default
flush_interval = 300   # 30x default
```

This configuration:
- ✅ Reduces writes by ~50x
- ✅ Significantly extends SD card life
- ✅ Minimal performance impact
- ⚠️ Risk: up to 5 minutes of data loss on crash
- ⚠️ Uses ~500KB-5MB RAM for batching

The built-in DuckDB optimizations further reduce write frequency without additional configuration.

