# Example Deployment Scripts

## Christmas Tree Water Monitor 🎄

The original use case! Monitor your Christmas tree's water level with proper over-engineering.

### Setup

1. **Build the Docker image with email alerts:**
   ```bash
   SMTP_SERVER=smtp.gmail.com \
   SMTP_PORT=587 \
   SMTP_FROM=your-email@gmail.com \
   SMTP_TO=your-email@gmail.com \
   SMTP_PASSWORD=your-app-password \
   ./build-docker.sh
   ```

2. **Run the Christmas tree monitor:**
   ```bash
   MQTT_BROKER=192.168.1.100 \
   ALERT_EMAIL=you@example.com \
   ./examples/christmas-tree-docker.sh
   ```

### Expected MQTT Topics

Your Christmas tree sensor should publish to:
- `christmas/tree/water/level` - Current water level (0-100%)
- `christmas/tree/water/status` - Status messages (ok, low, empty)
- `christmas/tree/status/temperature` - Tree stand temperature
- `christmas/tree/status/humidity` - Ambient humidity

### Query Your Tree's Data

```bash
# View recent water levels
duckdb tree-data/christmas_tree.db \
  "SELECT timestamp, payload as water_level 
   FROM water_level 
   ORDER BY timestamp DESC 
   LIMIT 24"

# Check if tree needs water
duckdb tree-data/christmas_tree.db \
  "SELECT timestamp, payload as water_level 
   FROM water_level 
   WHERE CAST(payload AS DOUBLE) < 30 
   ORDER BY timestamp DESC 
   LIMIT 1"

# Daily water consumption
duckdb tree-data/christmas_tree.db \
  "SELECT 
     DATE_TRUNC('day', timestamp) as day,
     MAX(CAST(payload AS DOUBLE)) - MIN(CAST(payload AS DOUBLE)) as consumed
   FROM water_level 
   GROUP BY day 
   ORDER BY day DESC"
```

### Grafana Dashboard

Create visualizations of your tree's hydration:

1. Install Grafana
2. Add DuckDB data source (via SQLite interface)
3. Create panels showing:
   - Current water level gauge
   - Water level over time (line chart)
   - Daily consumption (bar chart)
   - Days until tree runs dry (calculated field)

## Home Automation

Monitor all your home sensors:

```bash
docker run -d \
  --name home-sensors \
  --restart unless-stopped \
  -v /mnt/nas/home-sensors:/app/data \
  -e MQTT_BROKER=homeassistant.local \
  -e MQTT_USERNAME=mqtt \
  -e MQTT_PASSWORD=your-password \
  -e TOPICS="home/+/temperature:temps:Temperatures;home/+/humidity:humidity:Humidity;home/+/motion:motion:Motion;home/+/door:doors:Door sensors" \
  -e DB_BATCH_SIZE=1000 \
  -e DB_FLUSH_INTERVAL=60 \
  -e ALERT_EMAIL_TO=admin@example.com \
  -e ALERT_DB_SIZE_MB=5000 \
  mqtt-logger:latest
```

## IoT Device Fleet

Log all your IoT devices:

```bash
docker run -d \
  --name iot-fleet \
  --restart unless-stopped \
  -v $(pwd)/iot-data:/app/data \
  -e MQTT_BROKER=mqtt.myiot.com \
  -e MQTT_PORT=8883 \
  -e TOPICS="devices/+/metrics:metrics:Device metrics;devices/+/events:events:Device events;devices/+/logs:logs:Device logs" \
  -e LOG_LEVEL=DEBUG \
  -e DB_BATCH_SIZE=10000 \
  -e DB_FLUSH_INTERVAL=600 \
  mqtt-logger:latest
```

## Weather Station

Log weather data:

```bash
docker run -d \
  --name weather-station \
  --restart unless-stopped \
  -v $(pwd)/weather-data:/app/data \
  -e MQTT_BROKER=192.168.1.50 \
  -e TOPICS="weather/outdoor:outdoor:Outdoor sensors;weather/indoor:indoor:Indoor sensors;weather/forecast:forecast:Forecast data" \
  -e DB_PATH=/app/data/weather.db \
  mqtt-logger:latest
```

