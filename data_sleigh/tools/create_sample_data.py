#!/usr/bin/env python3
"""
Generate sample data for testing Data Sleigh.

Creates a DuckDB database with sample water level and YoLink sensor data.

Usage:
    python create_sample_data.py <output_db> [days]

Examples:
    python create_sample_data.py test.duckdb 1
    python create_sample_data.py /path/to/sample.duckdb 7
"""
import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path
from random import gauss, randint, uniform

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from data_sleigh.storage import MessageStore


def generate_water_level_data(store: MessageStore, days: int = 1):
    """Generate sample water level data.

    Args:
        store: MessageStore instance
        days: Number of days of data to generate
    """
    table_name = "water_level"

    print(f"Generating {days} days of water level data...")

    # Simulate water consumption with refills
    now = datetime.now()
    current_level = 10.0  # Start at 10mm (full)

    # Generate data points every minute
    total_points = days * 24 * 60

    for i in range(total_points):
        timestamp = now - timedelta(minutes=total_points - i)

        # Consumption rate: slowly increase (tree drinks water)
        # Average: 0.01mm per minute, ~14.4mm per day
        consumption = gauss(0.01, 0.002)
        current_level += consumption

        # Add some noise
        noisy_level = current_level + gauss(0, 0.5)

        # Clamp to reasonable bounds
        noisy_level = max(5.0, min(50.0, noisy_level))

        # Simulate refills (when level gets high, reset to low)
        if current_level > 45:
            current_level = uniform(8, 12)
            noisy_level = current_level

        # Store as bytes (simulating MQTT payload)
        payload = str(round(noisy_level, 2)).encode("utf-8")

        store.insert_message(
            table_name=table_name,
            topic="xmas/tree/water/raw",
            payload=payload,
            qos=1,
            retain=False,
        )

        # Flush periodically
        if i % 1000 == 0:
            store.flush(table_name)
            print(f"  Generated {i}/{total_points} water level points...")

    # Final flush
    store.flush(table_name)
    print(f"  ✓ Generated {total_points} water level data points")


def generate_yolink_data(store: MessageStore, days: int = 1):
    """Generate sample YoLink sensor data.

    Args:
        store: MessageStore instance
        days: Number of days of data to generate
    """
    table_name = "yolink_sensors"

    print(f"Generating {days} days of YoLink sensor data...")

    now = datetime.now()

    # Generate data points every 5 minutes for air sensor
    air_points = days * 24 * 12  # 12 per hour
    air_device_id = "d88b4c04000a9da6"
    base_temp_air = 72.0
    base_humidity = 45.0

    for i in range(air_points):
        timestamp = now - timedelta(minutes=5 * (air_points - i))

        # Simulate daily temperature variation
        hour_of_day = timestamp.hour + timestamp.minute / 60
        temp_variation = 3 * ((hour_of_day - 12) / 12)  # +/- 3 degrees through day
        temperature = base_temp_air + temp_variation + gauss(0, 0.5)

        # Humidity varies inversely with temperature
        humidity_variation = -2 * temp_variation
        humidity = base_humidity + humidity_variation + gauss(0, 2)
        humidity = max(20, min(80, humidity))

        battery = randint(95, 100)
        signal = randint(-55, -45)

        raw_data = {
            "event": "THSensor.Report",
            "deviceId": air_device_id,
            "data": {
                "temperature": temperature,
                "humidity": humidity,
                "battery": battery,
                "loraInfo": {"signal": signal},
            },
            "time": timestamp.isoformat(),
        }

        store.insert_yolink_message(
            device_type="air",
            device_id=air_device_id,
            temperature=temperature,
            humidity=humidity,
            battery=battery,
            signal=signal,
            raw_data=raw_data,
            table_name=table_name,
        )

        if i % 100 == 0:
            store.flush(table_name)
            print(f"  Generated {i}/{air_points} air sensor points...")

    # Generate data points every 10 minutes for water sensor
    water_points = days * 24 * 6  # 6 per hour
    water_device_id = "d88b4c010008bbe2"
    base_temp_water = 68.0

    for i in range(water_points):
        timestamp = now - timedelta(minutes=10 * (water_points - i))

        # Water temperature is more stable
        temperature = base_temp_water + gauss(0, 1.0)

        battery = randint(90, 100)
        signal = randint(-60, -50)

        raw_data = {
            "event": "THSensor.Report",
            "deviceId": water_device_id,
            "data": {
                "temperature": temperature,
                "humidity": 0,  # Water sensor doesn't measure humidity
                "battery": battery,
                "loraInfo": {"signal": signal},
            },
            "time": timestamp.isoformat(),
        }

        store.insert_yolink_message(
            device_type="water",
            device_id=water_device_id,
            temperature=temperature,
            humidity=None,
            battery=battery,
            signal=signal,
            raw_data=raw_data,
            table_name=table_name,
        )

        if i % 100 == 0:
            store.flush(table_name)
            print(f"  Generated {i}/{water_points} water sensor points...")

    # Final flush
    store.flush(table_name)
    print(f"  ✓ Generated {air_points} air + {water_points} water sensor data points")


def main():
    parser = argparse.ArgumentParser(
        description="Generate sample data for testing Data Sleigh"
    )
    parser.add_argument(
        "db_path",
        type=Path,
        help="Path to output DuckDB database file",
    )
    parser.add_argument(
        "days",
        type=int,
        nargs="?",
        default=1,
        help="Number of days of data to generate (default: 1)",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("🎄 Data Sleigh Sample Data Generator")
    print("=" * 60)
    print(f"Output:  {args.db_path}")
    print(f"Days:    {args.days}")
    print("=" * 60)
    print()

    # Create message store
    store = MessageStore(args.db_path, batch_size=100, flush_interval=10)

    # Create tables
    store.create_table("water_level")
    store.create_yolink_table("yolink_sensors")

    # Generate data
    generate_water_level_data(store, args.days)
    generate_yolink_data(store, args.days)

    # Close
    store.close()

    print()
    print("=" * 60)
    print("✓ Sample data generation complete!")
    print("=" * 60)
    print()
    print(f"Database created at: {args.db_path}")
    print(f"Size: {args.db_path.stat().st_size / (1024*1024):.2f} MB")
    print()
    print("Test with:")
    print(f"  python tools/generate_json.py {args.db_path}")


if __name__ == "__main__":
    main()


