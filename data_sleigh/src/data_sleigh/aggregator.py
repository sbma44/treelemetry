"""Data aggregation functions for water level and YoLink sensor data."""

import logging
from pathlib import Path
from typing import Any

import duckdb

logger = logging.getLogger(__name__)


def query_aggregated_data(
    conn: duckdb.DuckDBPyConnection,
    interval_minutes: int,
    lookback_hours: int | None,
) -> list[dict[str, Any]]:
    """Query aggregated water level data with statistical measures.

    Args:
        conn: DuckDB connection
        interval_minutes: Aggregation interval in minutes (e.g., 1, 5, 60)
        lookback_hours: How far back to query (e.g., 1, 24, or None for all data)

    Returns:
        List of aggregated measurement dictionaries with statistics
    """
    try:
        # Build the time window constraint
        if lookback_hours is not None:
            time_filter = f"timestamp >= latest.max_ts - INTERVAL '{lookback_hours} hours'"
        else:
            time_filter = "1=1"  # No time filter, get all data

        query = f"""
        WITH latest AS (
            SELECT MAX(timestamp) as max_ts
            FROM water_level
            WHERE topic = 'xmas/tree/water/raw'
        )
        SELECT
            time_bucket(INTERVAL '{interval_minutes} minutes', timestamp) as bucket_time,
            AVG(CAST(payload AS DOUBLE)) as mean,
            STDDEV_POP(CAST(payload AS DOUBLE)) as stddev,
            MIN(CAST(payload AS DOUBLE)) as min,
            MAX(CAST(payload AS DOUBLE)) as max,
            COUNT(*) as count
        FROM water_level, latest
        WHERE {time_filter}
        AND topic = 'xmas/tree/water/raw'
        AND payload IS NOT NULL
        GROUP BY bucket_time
        ORDER BY bucket_time ASC
        """

        result = conn.execute(query).fetchall()

        aggregates = []
        for row in result:
            bucket_time = row[0]
            mean = row[1]
            stddev = row[2]
            min_val = row[3]
            max_val = row[4]
            count = row[5]

            # Only include if we have valid data
            if mean is not None:
                aggregates.append({
                    "t": bucket_time.isoformat() if hasattr(bucket_time, 'isoformat') else str(bucket_time),
                    "m": round(float(mean), 2),
                    "s": round(float(stddev), 3) if stddev is not None else 0,
                    "n": int(count),
                    "min": round(float(min_val), 2),
                    "max": round(float(max_val), 2),
                })

        return aggregates

    except Exception as e:
        logger.error(f"ERROR querying aggregated data: {e}")
        raise


def query_yolink_aggregated_data(
    conn: duckdb.DuckDBPyConnection,
    interval_minutes: int,
    lookback_hours: int | None,
) -> dict[str, list[dict[str, Any]]]:
    """Query aggregated YoLink sensor data (temperature/humidity) with statistical measures.

    Uses the normalized YoLink table schema with separate columns for easy querying.

    Args:
        conn: DuckDB connection
        interval_minutes: Aggregation interval in minutes (e.g., 1, 5, 60)
        lookback_hours: How far back to query (e.g., 1, 24, or None for all data)

    Returns:
        Dictionary with 'air' and 'water' keys, each containing a list of
        aggregated measurement dictionaries with temperature (and humidity for air).
    """
    try:
        # Check if yolink_sensors table exists
        tables = conn.execute("SHOW TABLES").fetchall()
        table_names = [t[0] for t in tables]
        if "yolink_sensors" not in table_names:
            return {"air": [], "water": []}

        # Build the time window constraint
        if lookback_hours is not None:
            time_filter = f"timestamp >= latest.max_ts - INTERVAL '{lookback_hours} hours'"
        else:
            time_filter = "1=1"  # No time filter, get all data

        results = {"air": [], "water": []}

        for device_type in ["air", "water"]:
            # Query using normalized columns (much simpler than JSON extraction!)
            query = f"""
            WITH latest AS (
                SELECT MAX(timestamp) as max_ts
                FROM yolink_sensors
            )
            SELECT
                time_bucket(INTERVAL '{interval_minutes} minutes', timestamp) as bucket_time,
                AVG(temperature) as temp_mean,
                STDDEV_POP(temperature) as temp_stddev,
                MIN(temperature) as temp_min,
                MAX(temperature) as temp_max,
                AVG(humidity) as humidity_mean,
                STDDEV_POP(humidity) as humidity_stddev,
                MIN(humidity) as humidity_min,
                MAX(humidity) as humidity_max,
                COUNT(*) as count
            FROM yolink_sensors, latest
            WHERE {time_filter}
            AND device_type = '{device_type}'
            AND temperature IS NOT NULL
            GROUP BY bucket_time
            ORDER BY bucket_time ASC
            """

            result = conn.execute(query).fetchall()

            aggregates = []
            for row in result:
                bucket_time = row[0]
                temp_mean = row[1]
                temp_stddev = row[2]
                temp_min = row[3]
                temp_max = row[4]
                humidity_mean = row[5]
                humidity_stddev = row[6]
                humidity_min = row[7]
                humidity_max = row[8]
                count = row[9]

                # Only include if we have valid temperature data
                if temp_mean is not None:
                    entry = {
                        "t": bucket_time.isoformat() if hasattr(bucket_time, 'isoformat') else str(bucket_time),
                        "temp": {
                            "m": round(float(temp_mean), 2),
                            "s": round(float(temp_stddev), 3) if temp_stddev is not None else 0,
                            "min": round(float(temp_min), 2),
                            "max": round(float(temp_max), 2),
                        },
                        "n": int(count),
                    }

                    # Only include humidity for air sensor (and if we have valid data)
                    if device_type == "air" and humidity_mean is not None:
                        entry["humidity"] = {
                            "m": round(float(humidity_mean), 2),
                            "s": round(float(humidity_stddev), 3) if humidity_stddev is not None else 0,
                            "min": round(float(humidity_min), 2),
                            "max": round(float(humidity_max), 2),
                        }

                    aggregates.append(entry)

            results[device_type] = aggregates

        return results

    except Exception as e:
        logger.error(f"ERROR querying YoLink aggregated data: {e}")
        return {"air": [], "water": []}


def query_water_levels(
    conn: duckdb.DuckDBPyConnection,
    minutes: int = 10
) -> list[dict[str, Any]]:
    """Query the most recent water level measurements.

    Args:
        conn: DuckDB connection
        minutes: Number of minutes of historical data to retrieve

    Returns:
        List of measurement dictionaries
    """
    try:
        # Query the MQTT log format
        # Note: We use the MAX(timestamp) approach instead of NOW() to avoid
        # timezone issues between the database timestamps and system time
        query = f"""
        WITH latest AS (
            SELECT MAX(timestamp) as max_ts
            FROM water_level
            WHERE topic = 'xmas/tree/water/raw'
        )
        SELECT
            timestamp,
            CAST(payload AS DOUBLE) as water_level_mm
        FROM water_level, latest
        WHERE timestamp >= latest.max_ts - INTERVAL '{minutes} minutes'
        AND topic = 'xmas/tree/water/raw'
        ORDER BY timestamp ASC
        """

        result = conn.execute(query).fetchall()

        measurements = []
        for row in result:
            measurements.append({
                "timestamp": row[0].isoformat() if hasattr(row[0], 'isoformat') else str(row[0]),
                "water_level_mm": float(row[1]) if row[1] is not None else None,
            })

        return measurements

    except Exception as e:
        logger.error(f"ERROR querying water levels: {e}")
        raise


