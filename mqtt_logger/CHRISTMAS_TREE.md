# 🎄 Christmas Tree Water Level Monitor

*Because nothing says "holiday spirit" like over-engineering your Christmas tree hydration system!*

This guide shows you how to deploy the MQTT Logger specifically for monitoring your Christmas tree's water level.

## The Setup

Your Christmas tree has:
- An ESP8266/ESP32 with a water level sensor
- Publishing to MQTT topics like `christmas/tree/water/level`
- You want to log this data and get alerts when the tree needs water
- Running on your NAS because the Raspberry Pi OOM'd trying to build DuckDB

## Quick Deploy to NAS

### 1. Build the Image with Email Alerts

```bash
cd mqtt-logger

# Build with Gmail alerts
SMTP_SERVER=smtp.gmail.com \
SMTP_PORT=587 \
SMTP_FROM=your-email@gmail.com \
SMTP_TO=your-email@gmail.com \
SMTP_PASSWORD=your-app-password \
./build-docker.sh
```

**Gmail App Password Setup:**
1. Go to https://myaccount.google.com/apppasswords
2. Select "Mail" and "Other (Custom name)"
3. Name it "MQTT Logger"
4. Copy the 16-character password

### 2. Deploy the Container

```bash
# Create data directory
mkdir -p ~/christmas-tree-data

# Run the container
docker run -d \
  --name christmas-tree \
  --restart unless-stopped \
  -v ~/christmas-tree-data:/app/data \
  -e TZ=America/New_York \
  -e MQTT_BROKER=192.168.1.100 \
  -e TOPICS="christmas/tree/water/#:water_level:Tree water level" \
  -e DB_PATH=/app/data/tree.db \
  -e ALERT_EMAIL_TO=you@example.com \
  -e ALERT_DB_SIZE_MB=100 \
  mqtt-logger:latest
```

### 3. Verify It's Working

```bash
# Check logs
docker logs -f christmas-tree

# Should see:
# Generating configuration from environment variables...
# Connected to MQTT broker
# Subscribed to topic: christmas/tree/water/#
# MQTT Logger is running...
```

## Environment Variables for Christmas Tree

| Variable | Value | Why |
|----------|-------|-----|
| `MQTT_BROKER` | `192.168.1.100` | Your MQTT broker IP |
| `TOPICS` | `christmas/tree/water/#:water_level:Tree water` | Log all tree water topics |
| `DB_PATH` | `/app/data/tree.db` | Where to store the data |
| `DB_BATCH_SIZE` | `5000` (default) | Batch writes for NAS longevity |
| `DB_FLUSH_INTERVAL` | `300` (default) | Write every 5 minutes |
| `ALERT_EMAIL_TO` | `you@example.com` | Get alerts |
| `ALERT_DB_SIZE_MB` | `100` | Alert if DB > 100MB |
| `TZ` | `America/New_York` | Your timezone |

## Query Your Tree's Status

### Install DuckDB CLI

```bash
# On your NAS/Mac
brew install duckdb

# Or download from https://duckdb.org/docs/installation/
```

### Check Current Water Level

```bash
duckdb ~/christmas-tree-data/tree.db \
  "SELECT timestamp, payload as water_level
   FROM water_level
   ORDER BY timestamp DESC
   LIMIT 1"
```

### View Last 24 Hours

```bash
duckdb ~/christmas-tree-data/tree.db \
  "SELECT
     DATE_TRUNC('hour', timestamp) as hour,
     AVG(CAST(payload AS DOUBLE)) as avg_level
   FROM water_level
   WHERE timestamp >= NOW() - INTERVAL '24 hours'
   GROUP BY hour
   ORDER BY hour"
```

### Check if Tree Needs Water

```bash
duckdb ~/christmas-tree-data/tree.db \
  "SELECT timestamp, CAST(payload AS DOUBLE) as level
   FROM water_level
   WHERE CAST(payload AS DOUBLE) < 30
   ORDER BY timestamp DESC
   LIMIT 1"
```

### Calculate Days Until Empty

```bash
duckdb ~/christmas-tree-data/tree.db \
  "WITH recent_data AS (
     SELECT
       timestamp,
       CAST(payload AS DOUBLE) as level
     FROM water_level
     WHERE timestamp >= NOW() - INTERVAL '24 hours'
     ORDER BY timestamp
   ),
   consumption AS (
     SELECT
       (MAX(level) - MIN(level)) / 24.0 as hourly_rate
     FROM recent_data
   )
   SELECT
     current.level as current_level,
     cons.hourly_rate as hourly_consumption,
     current.level / NULLIF(cons.hourly_rate, 0) as hours_until_empty,
     current.level / NULLIF(cons.hourly_rate, 0) / 24.0 as days_until_empty
   FROM (
     SELECT CAST(payload AS DOUBLE) as level
     FROM water_level
     ORDER BY timestamp DESC
     LIMIT 1
   ) current, consumption cons"
```

## Advanced: Multiple Sensors

If you have multiple sensors:

```bash
docker run -d \
  --name christmas-tree \
  --restart unless-stopped \
  -v ~/christmas-tree-data:/app/data \
  -e MQTT_BROKER=192.168.1.100 \
  -e TOPICS="christmas/tree/water/#:water_level:Water;christmas/tree/temp/#:temperature:Temp;christmas/tree/lights/#:lights:Lights" \
  -e ALERT_EMAIL_TO=you@example.com \
  mqtt-logger:latest
```

Then query each sensor:

```bash
# Water level
duckdb tree.db "SELECT * FROM water_level ORDER BY timestamp DESC LIMIT 10"

# Temperature
duckdb tree.db "SELECT * FROM temperature ORDER BY timestamp DESC LIMIT 10"

# Lights status
duckdb tree.db "SELECT * FROM lights ORDER BY timestamp DESC LIMIT 10"
```

## Alerts

You'll receive email alerts when:
- **Database > 100MB**: "Your tree logs are getting large!"
- **Free space < 2GB**: "Your NAS is running out of space!"

Alerts are rate-limited to once per 24 hours to avoid spam.

## Grafana Dashboard (Optional)

### 1. Install Grafana

```bash
docker run -d \
  --name grafana \
  -p 3000:3000 \
  -v ~/grafana-data:/var/lib/grafana \
  grafana/grafana
```

### 2. Add DuckDB as Data Source

Use the SQLite plugin (DuckDB is compatible):
1. Go to http://your-nas:3000
2. Configuration → Data Sources → Add SQLite
3. Path: `/var/lib/grafana/tree.db`
4. Mount the database: `-v ~/christmas-tree-data:/var/lib/grafana`

### 3. Create Panels

**Current Water Level (Gauge):**
```sql
SELECT CAST(payload AS DOUBLE) as value
FROM water_level
ORDER BY timestamp DESC
LIMIT 1
```

**Water Level Over Time (Time Series):**
```sql
SELECT
  timestamp,
  CAST(payload AS DOUBLE) as water_level
FROM water_level
WHERE timestamp >= NOW() - INTERVAL '7 days'
ORDER BY timestamp
```

**Daily Consumption (Bar Chart):**
```sql
SELECT
  DATE_TRUNC('day', timestamp) as day,
  MAX(CAST(payload AS DOUBLE)) - MIN(CAST(payload AS DOUBLE)) as consumed
FROM water_level
GROUP BY day
ORDER BY day DESC
```

## Troubleshooting

### No Data Being Logged

```bash
# Check container is running
docker ps | grep christmas-tree

# Check logs
docker logs christmas-tree

# Verify MQTT connection
docker logs christmas-tree | grep -i "connected to mqtt"

# Test MQTT manually
mosquitto_sub -h 192.168.1.100 -t 'christmas/tree/#' -v
```

### Wrong Timezone

```bash
# Check current timezone
docker exec christmas-tree date

# Update container
docker stop christmas-tree
docker rm christmas-tree

# Run with correct TZ
docker run -d --name christmas-tree -e TZ=America/Los_Angeles ...
```

### Container Keeps Restarting

```bash
# Check logs for errors
docker logs christmas-tree

# Common issues:
# - MQTT broker unreachable
# - Invalid topic format
# - Permission issues with volume
```

## Maintenance

### Backup Your Data

```bash
# Backup database
cp ~/christmas-tree-data/tree.db ~/backups/tree-$(date +%Y%m%d).db

# Or automated
echo "0 2 * * * cp ~/christmas-tree-data/tree.db ~/backups/tree-\$(date +\%Y\%m\%d).db" | crontab -
```

### Clean Old Data

```bash
# Archive data older than 1 year
duckdb ~/christmas-tree-data/tree.db \
  "COPY (SELECT * FROM water_level WHERE timestamp < NOW() - INTERVAL '1 year')
   TO 'archive-2023.parquet' (FORMAT PARQUET)"

# Delete old data
duckdb ~/christmas-tree-data/tree.db \
  "DELETE FROM water_level WHERE timestamp < NOW() - INTERVAL '1 year'"

# Vacuum to reclaim space
duckdb ~/christmas-tree-data/tree.db "VACUUM"
```

### Update Container

```bash
# Rebuild image
./build-docker.sh

# Stop old container
docker stop christmas-tree
docker rm christmas-tree

# Start new container (same command as before)
docker run -d --name christmas-tree ...
```

## Cost Analysis

**Why this over-engineering is actually justified:**

| Aspect | Cost | Benefit |
|--------|------|---------|
| Dead tree replacement | $50+ | Water alerts prevent tree death |
| Water damage to floor | $$$$ | Never forget to check water |
| Peace of mind | Priceless | Data-driven tree hydration |
| Bragging rights | Free | "I monitor my tree via MQTT" |
| Learning experience | Time | Docker + MQTT + DuckDB skills |

## Next Level Ideas

1. **Predictive Alerts**: ML model to predict when tree will run dry
2. **Auto-refill**: Pump connected to MQTT to auto-fill water
3. **Family Dashboard**: Share Grafana dashboard with family
4. **Historical Analysis**: Compare water usage year-over-year
5. **Integration**: Trigger lights to red when water is low
6. **Voice Alerts**: "Alexa, does the tree need water?"

## Conclusion

Your Christmas tree is now more monitored than most production systems. 🎄

Happy holidays, and may your tree never run dry!

---

*P.S. - This is absolutely overkill, and that's what makes it perfect.*

