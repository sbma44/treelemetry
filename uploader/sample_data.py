#!/usr/bin/env python3
"""
Sample data generator for testing Treelemetry.

Creates a DuckDB database with sample water level measurements matching the
MQTT log format used by the actual sensor system.

This creates a table structure matching mqtt_logs.db:
- Table: water_level
- Columns: id, timestamp, topic, payload, qos, retain
"""
import duckdb
from datetime import datetime, timedelta
import random
import math


def generate_sample_data(db_path: str = "tree.duckdb", days: int = 7):
    """
    Generate sample water level data for testing.
    
    Creates a table matching the MQTT log format where the water level
    measurement is stored in the payload field as a string.

    Args:
        db_path: Path where the DuckDB file will be created
        days: Number of days of sample data to generate (default 7 for testing aggregates)
    """
    conn = duckdb.connect(db_path)

    # Create the water_level table matching the MQTT log format
    conn.execute("""
        CREATE SEQUENCE IF NOT EXISTS water_level_id_seq START 1;
    """)
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS water_level (
            id INTEGER PRIMARY KEY DEFAULT nextval('water_level_id_seq'),
            timestamp TIMESTAMP NOT NULL,
            topic VARCHAR NOT NULL,
            payload VARCHAR,
            qos INTEGER,
            retain BOOLEAN
        )
    """)

    print(f"Generating {days} days of sample data...")

    # Generate data points every 3 seconds (matching ~3s MQTT publish rate)
    now = datetime.now()
    start_time = now - timedelta(days=days)

    measurements = []

    # Simulate a realistic water level pattern
    base_level = 25.0  # Starting water level in mm (matching observed data range)
    current_level = base_level

    current_time = start_time
    interval = timedelta(seconds=3)

    while current_time <= now:
        # Simulate gradual water consumption (downward trend)
        # with some random fluctuations
        hours_elapsed = (current_time - start_time).total_seconds() / 3600

        # Water decreases over time with a daily cycle
        # (faster consumption during "day" hours)
        hour_of_day = current_time.hour
        day_factor = 1.0 + 0.5 * math.sin((hour_of_day - 6) * math.pi / 12)

        # Gradual decrease + daily cycle + random noise
        trend = -0.02 * hours_elapsed  # Slow decrease over time
        daily_variation = 2 * math.sin(hours_elapsed * 2 * math.pi / 24)
        noise = random.gauss(0, 0.3)

        current_level = max(0, base_level + trend + daily_variation + noise)

        # Format payload as string with 2 decimal places (matching MQTT format)
        payload = f"{current_level:.2f}"

        measurements.append((
            current_time,
            "xmas/tree/water/raw",
            payload,
            0,  # qos
            False,  # retain
        ))

        current_time += interval

    # Insert all measurements
    conn.executemany(
        "INSERT INTO water_level (timestamp, topic, payload, qos, retain) VALUES (?, ?, ?, ?, ?)",
        measurements
    )

    conn.commit()

    # Print summary
    result = conn.execute("""
        SELECT
            COUNT(*) as count,
            MIN(CAST(payload AS DOUBLE)) as min_level,
            MAX(CAST(payload AS DOUBLE)) as max_level,
            AVG(CAST(payload AS DOUBLE)) as avg_level,
            MIN(timestamp) as first_timestamp,
            MAX(timestamp) as last_timestamp
        FROM water_level
    """).fetchone()

    print(f"\nSample data generated successfully!")
    print(f"Database: {db_path}")
    print(f"Total measurements: {result[0]}")
    print(f"Water level range: {result[1]:.1f} - {result[2]:.1f} mm")
    print(f"Average level: {result[3]:.1f} mm")
    print(f"Time range: {result[4]} to {result[5]}")

    conn.close()


if __name__ == "__main__":
    import sys

    db_path = sys.argv[1] if len(sys.argv) > 1 else "tree.duckdb"
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 7

    generate_sample_data(db_path, days)

    print(f"\nTo test the uploader with this data:")
    print(f"  export DUCKDB_PATH={db_path}")
    print(f"  uv run python src/uploader.py")

