#!/usr/bin/env python3
"""
Treelemetry Uploader

Queries water level data from DuckDB and uploads it to S3 for public access.
Runs as a long-running daemon with configurable upload intervals.
"""
import gzip
import json
import math
import os
import sys
import signal
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import boto3
import duckdb
import numpy as np
import pandas as pd
from dateutil.parser import parse as parse_date
from dotenv import load_dotenv
from scipy.signal import find_peaks
from sklearn.linear_model import LinearRegression

# Load environment variables from .env file if it exists
load_dotenv()

# Global flag for graceful shutdown
shutdown_requested = False


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    global shutdown_requested
    print(f"\nReceived signal {signum}, shutting down gracefully...")
    shutdown_requested = True


def get_env_or_exit(var_name: str) -> str:
    """Get environment variable or exit with error."""
    value = os.getenv(var_name)
    if not value:
        print(f"ERROR: Environment variable {var_name} is required", file=sys.stderr)
        sys.exit(1)
    return value


@contextmanager
def get_db_connection(db_path: Path):
    """
    Establish connection to DuckDB with fallback strategies.

    This is a context manager that ensures proper cleanup of resources,
    especially temporary database copies created when file locking fails.

    Args:
        db_path: Path to the DuckDB database file

    Yields:
        DuckDB connection object

    Example:
        with get_db_connection(db_path) as conn:
            result = conn.execute("SELECT * FROM table").fetchall()
    """
    import tempfile
    import shutil

    conn = None
    tmp_path = None

    try:
        # Approach 1: Try with read_only mode and explicit config
        try:
            config = {'access_mode': 'READ_ONLY'}
            conn = duckdb.connect(str(db_path), read_only=True, config=config)
            yield conn
        except duckdb.IOException:
            # Approach 2: If locking fails, copy the file to temp location
            # This is slower but works reliably with Docker volume mounts
            print("  Note: Using temporary copy due to lock constraints")

            with tempfile.NamedTemporaryFile(suffix='.duckdb', delete=False) as tmp:
                tmp_path = tmp.name

            shutil.copy2(db_path, tmp_path)
            conn = duckdb.connect(tmp_path, read_only=True)
            yield conn
    finally:
        # Ensure connection is closed
        if conn:
            try:
                conn.close()
            except Exception as e:
                print(f"  Warning: Error closing connection: {e}", file=sys.stderr)

        # Clean up temp file immediately if it was created
        if tmp_path:
            try:
                Path(tmp_path).unlink(missing_ok=True)
                print(f"  Cleaned up temporary database copy: {tmp_path}")
            except Exception as e:
                print(f"  Warning: Could not delete temp file {tmp_path}: {e}", file=sys.stderr)


def query_water_levels(db_path: Path, minutes: int = 10) -> List[Dict[str, Any]]:
    """
    Query the most recent water level measurements from DuckDB.

    Args:
        db_path: Path to the DuckDB database file
        minutes: Number of minutes of historical data to retrieve

    Returns:
        List of measurement dictionaries
    """
    try:
        with get_db_connection(db_path) as conn:
            # Query the MQTT log format:
            # CREATE TABLE water_level (
            #     id INTEGER PRIMARY KEY,
            #     timestamp TIMESTAMP NOT NULL,
            #     topic VARCHAR NOT NULL,
            #     payload VARCHAR,
            #     qos INTEGER,
            #     retain BOOLEAN
            # )
            #
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

    except duckdb.IOException as e:
        # Handle database lock or access issues specifically
        print(f"ERROR: Database access issue (may be locked): {e}", file=sys.stderr)
        print("  Tip: Ensure the database file is mounted read-only in Docker", file=sys.stderr)
        raise
    except Exception as e:
        print(f"ERROR querying DuckDB: {e}", file=sys.stderr)
        raise


def query_aggregated_data(
    db_path: Path,
    interval_minutes: int,
    lookback_hours: int,
) -> List[Dict[str, Any]]:
    """
    Query aggregated water level data with statistical measures.

    Args:
        db_path: Path to the DuckDB database file
        interval_minutes: Aggregation interval in minutes (e.g., 1, 5, 60)
        lookback_hours: How far back to query (e.g., 1, 24, or None for all data)

    Returns:
        List of aggregated measurement dictionaries with statistics
    """
    try:
        with get_db_connection(db_path) as conn:
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
        print(f"ERROR querying aggregated data: {e}", file=sys.stderr)
        raise


def query_yolink_aggregated_data(
    db_path: Path,
    interval_minutes: int,
    lookback_hours: int | None,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Query aggregated YoLink sensor data (temperature/humidity) with statistical measures.

    Args:
        db_path: Path to the DuckDB database file
        interval_minutes: Aggregation interval in minutes (e.g., 1, 5, 60)
        lookback_hours: How far back to query (e.g., 1, 24, or None for all data)

    Returns:
        Dictionary with 'air' and 'water' keys, each containing a list of
        aggregated measurement dictionaries with temperature (and humidity for air).
    """
    try:
        with get_db_connection(db_path) as conn:
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
                # Query to aggregate YoLink sensor data
                # The payload is JSON stored as VARCHAR with structure:
                # {"device_type": "air/water", "temperature": float, "humidity": float|null, ...}
                query = f"""
                WITH latest AS (
                    SELECT MAX(timestamp) as max_ts
                    FROM yolink_sensors
                ),
                parsed AS (
                    SELECT
                        timestamp,
                        json_extract(payload, '$.temperature')::DOUBLE as temperature,
                        json_extract(payload, '$.humidity')::DOUBLE as humidity
                    FROM yolink_sensors, latest
                    WHERE {time_filter}
                    AND topic LIKE 'yolink/{device_type}/%'
                    AND payload IS NOT NULL
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
                FROM parsed
                WHERE temperature IS NOT NULL
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
        print(f"ERROR querying YoLink aggregated data: {e}", file=sys.stderr)
        return {"air": [], "water": []}


def calculate_stats(measurements: List[Dict[str, Any]]) -> Dict[str, float]:
    """Calculate statistics from measurements."""
    if not measurements:
        return {}

    levels = [m["water_level_mm"] for m in measurements if m["water_level_mm"] is not None]

    if not levels:
        return {}

    # Calculate mean
    mean = sum(levels) / len(levels)

    # Calculate standard deviation
    variance = sum((x - mean) ** 2 for x in levels) / len(levels)
    stddev = math.sqrt(variance)

    return {
        "min_level": min(levels),
        "max_level": max(levels),
        "avg_level": mean,
        "stddev": stddev,
        "measurement_count": len(levels),
    }


def analyze_water_level_segments(db_path: Path) -> Optional[Dict[str, Any]]:
    """
    Analyze water level data to detect consumption segments and predict refill time.

    Returns:
        Dictionary containing segments, extrema, and current prediction
    """
    try:
        with get_db_connection(db_path) as conn:
            # Query all historical data for analysis
            query = """
            SELECT
                timestamp,
                CAST(payload AS DOUBLE) as distance_mm
            FROM water_level
            WHERE topic = 'xmas/tree/water/raw'
              AND payload IS NOT NULL
            ORDER BY timestamp ASC
            """

            df = conn.execute(query).df()

        if len(df) < 100:  # Need sufficient data for analysis
            return None

        # Basic preprocessing
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.dropna(subset=["timestamp", "distance_mm"])
        df = df.sort_values("timestamp")

        # Outlier removal via rolling-median + MAD
        ROLL_WIN = "5min"
        MAD_MULTIPLIER = 6.0

        ts_indexed = df.set_index("timestamp")
        local_median = (
            ts_indexed["distance_mm"]
            .rolling(ROLL_WIN, center=True, min_periods=1)
            .median()
        )

        df["local_median"] = local_median.values
        df["residual"] = df["distance_mm"] - df["local_median"]

        residuals = df["residual"].dropna()
        mad = np.median(np.abs(residuals - residuals.median()))
        if mad == 0:
            mad = residuals.std(ddof=0)

        threshold = MAD_MULTIPLIER * mad
        df["is_outlier"] = df["residual"].abs() > threshold
        df_clean = df.loc[~df["is_outlier"]].copy()

        if len(df_clean) < 50:
            return None

        # Smoothing for analysis and extrema detection
        SMOOTH_WIN = "10min"
        ts_clean = df_clean.set_index("timestamp")
        df_clean["distance_smooth"] = (
            ts_clean["distance_mm"]
            .rolling(SMOOTH_WIN, center=True, min_periods=1)
            .median()
            .values
        )

        df_clean = df_clean.dropna(subset=["distance_smooth"]).reset_index(drop=True)
        df_clean["index"] = df_clean.index

        # Detect local minima and maxima
        PROMINENCE_MM = 5.0
        MIN_PEAK_DISTANCE_SAMPLES = 20

        series = df_clean["distance_smooth"].to_numpy()

        # Maxima (local peaks)
        max_idx, _ = find_peaks(
            series,
            prominence=PROMINENCE_MM,
            distance=MIN_PEAK_DISTANCE_SAMPLES
        )

        # Minima: peaks of inverted series
        min_idx, _ = find_peaks(
            -series,
            prominence=PROMINENCE_MM,
            distance=MIN_PEAK_DISTANCE_SAMPLES
        )

        maxima = df_clean.iloc[max_idx][["timestamp", "distance_smooth"]].copy()
        minima = df_clean.iloc[min_idx][["timestamp", "distance_smooth"]].copy()

        # Build segments: rising between a minimum and next maximum
        MIN_SEG_DURATION = pd.Timedelta("3h")
        MIN_SEG_POINTS = 20

        segments = []
        max_idx_sorted = np.sort(max_idx)
        min_idx_sorted = np.sort(min_idx)

        for mn in min_idx_sorted:
            after = max_idx_sorted[max_idx_sorted > mn]
            if len(after) == 0:
                # This is the current segment - handle separately
                continue
            mx = after[0]

            seg = df_clean[(df_clean["index"] >= mn) & (df_clean["index"] <= mx)].copy()
            if len(seg) < MIN_SEG_POINTS:
                continue

            duration = seg["timestamp"].iloc[-1] - seg["timestamp"].iloc[0]
            if duration < MIN_SEG_DURATION:
                continue

            segments.append({
                "min_index": mn,
                "max_index": mx,
                "data": seg
            })

        # Calculate slopes for each completed segment
        segment_list = []
        for i, seg_info in enumerate(segments, start=1):
            seg = seg_info["data"]

            t0 = seg["timestamp"].iloc[0]
            x_hours = (seg["timestamp"] - t0).dt.total_seconds().values.reshape(-1, 1) / 3600.0
            y = seg["distance_smooth"].values

            model = LinearRegression().fit(x_hours, y)
            slope = model.coef_[0]  # mm/hour

            # Only include rising segments (consumption)
            if slope > 0:
                segment_list.append({
                    "id": i,
                    "start_time": seg["timestamp"].iloc[0].isoformat(),
                    "end_time": seg["timestamp"].iloc[-1].isoformat(),
                    "start_distance_mm": round(float(seg["distance_smooth"].iloc[0]), 2),
                    "end_distance_mm": round(float(seg["distance_smooth"].iloc[-1]), 2),
                    "slope_mm_per_hr": round(float(slope), 3),
                    "duration_hours": round((seg["timestamp"].iloc[-1] - seg["timestamp"].iloc[0]).total_seconds() / 3600.0, 2),
                    "n_points": len(seg),
                    "is_current": False
                })

        # Handle current segment (from last minimum to now)
        current_prediction = None
        if len(min_idx_sorted) > 0:
            last_min = min_idx_sorted[-1]
            current_seg = df_clean[df_clean["index"] >= last_min].copy()

            if len(current_seg) >= MIN_SEG_POINTS:
                duration = current_seg["timestamp"].iloc[-1] - current_seg["timestamp"].iloc[0]

                if duration >= pd.Timedelta("1h"):  # At least 1 hour for current segment
                    t0 = current_seg["timestamp"].iloc[0]
                    x_hours = (current_seg["timestamp"] - t0).dt.total_seconds().values.reshape(-1, 1) / 3600.0
                    y = current_seg["distance_smooth"].values

                    model = LinearRegression().fit(x_hours, y)
                    slope = model.coef_[0]

                    if slope > 0:
                        current_distance = float(current_seg["distance_smooth"].iloc[-1])
                        remaining_mm = 50.0 - current_distance

                        if remaining_mm > 0:
                            hours_to_50mm = remaining_mm / slope
                            predicted_time = current_seg["timestamp"].iloc[-1] + pd.Timedelta(hours=hours_to_50mm)

                            current_prediction = {
                                "current_distance_mm": round(current_distance, 2),
                                "slope_mm_per_hr": round(float(slope), 3),
                                "time_to_50mm_hours": round(hours_to_50mm, 2),
                                "predicted_refill_time": predicted_time.isoformat()
                            }

                        # Add current segment to segment list
                        segment_list.append({
                            "id": len(segment_list) + 1,
                            "start_time": current_seg["timestamp"].iloc[0].isoformat(),
                            "end_time": current_seg["timestamp"].iloc[-1].isoformat(),
                            "start_distance_mm": round(float(current_seg["distance_smooth"].iloc[0]), 2),
                            "end_distance_mm": round(float(current_seg["distance_smooth"].iloc[-1]), 2),
                            "slope_mm_per_hr": round(float(slope), 3),
                            "duration_hours": round((current_seg["timestamp"].iloc[-1] - current_seg["timestamp"].iloc[0]).total_seconds() / 3600.0, 2),
                            "n_points": len(current_seg),
                            "is_current": True
                        })

        # Convert extrema to JSON-serializable format
        extrema = {
            "minima": [
                {
                    "timestamp": row["timestamp"].isoformat(),
                    "distance_mm": round(float(row["distance_smooth"]), 2)
                }
                for _, row in minima.iterrows()
            ],
            "maxima": [
                {
                    "timestamp": row["timestamp"].isoformat(),
                    "distance_mm": round(float(row["distance_smooth"]), 2)
                }
                for _, row in maxima.iterrows()
            ]
        }

        return {
            "segments": segment_list,
            "extrema": extrema,
            "current_prediction": current_prediction
        }

    except Exception as e:
        print(f"  Warning: Could not perform segment analysis: {e}")
        return None


def create_json_output(
    measurements: List[Dict[str, Any]],
    aggregates_1m: Optional[List[Dict[str, Any]]] = None,
    aggregates_5m: Optional[List[Dict[str, Any]]] = None,
    aggregates_1h: Optional[List[Dict[str, Any]]] = None,
    analysis: Optional[Dict[str, Any]] = None,
    yolink_1m: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    yolink_5m: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    yolink_1h: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    replay_delay: int = 300,
) -> Dict[str, Any]:
    """
    Create the JSON structure to upload.

    Args:
        measurements: List of raw measurement dictionaries (last 10 minutes)
        aggregates_1m: 1-minute aggregates for last hour
        aggregates_5m: 5-minute aggregates for last 24 hours
        aggregates_1h: 1-hour aggregates for all historical data
        analysis: Segment analysis with slopes and predictions
        yolink_1m: YoLink sensor 1-minute aggregates for last hour
        yolink_5m: YoLink sensor 5-minute aggregates for last 24 hours
        yolink_1h: YoLink sensor 1-hour aggregates for all historical data
        replay_delay: Delay in seconds for "realtime" replay visualization

    Returns:
        Dictionary ready for JSON serialization
    """
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "measurements": measurements,
        "replay_delay_seconds": replay_delay,
        "stats": calculate_stats(measurements),
    }

    # Add aggregated series if available
    # Format: compact key names for gzip efficiency
    # t=timestamp, m=mean, s=stddev, n=count, min/max=range
    if aggregates_1m:
        output["agg_1m"] = {
            "interval_minutes": 1,
            "lookback_hours": 1,
            "data": aggregates_1m,
        }

    if aggregates_5m:
        output["agg_5m"] = {
            "interval_minutes": 5,
            "lookback_hours": 24,
            "data": aggregates_5m,
        }

    if aggregates_1h:
        output["agg_1h"] = {
            "interval_minutes": 60,
            "lookback_hours": None,  # All historical data
            "data": aggregates_1h,
        }

    # Add segment analysis if available
    if analysis:
        output["analysis"] = analysis

    # Add YoLink sensor data if available
    # Structure: yolink_sensors.{interval}.{device_type} = [{t, temp:{m,s,min,max}, humidity?:{m,s,min,max}, n}, ...]
    yolink_data = {}

    def add_yolink_interval(key: str, data: Optional[Dict[str, List]], interval_minutes: int, lookback_hours: Optional[int]):
        if data and (data.get("air") or data.get("water")):
            yolink_data[key] = {
                "interval_minutes": interval_minutes,
                "lookback_hours": lookback_hours,
            }
            if data.get("air"):
                yolink_data[key]["air"] = data["air"]
            if data.get("water"):
                yolink_data[key]["water"] = data["water"]

    add_yolink_interval("agg_1m", yolink_1m, 1, 1)
    add_yolink_interval("agg_5m", yolink_5m, 5, 24)
    add_yolink_interval("agg_1h", yolink_1h, 60, None)

    if yolink_data:
        output["yolink_sensors"] = yolink_data

    return output


def upload_to_s3(
    data: Dict[str, Any],
    bucket: str,
    key: str,
    aws_access_key: str,
    aws_secret_key: str,
    cache_control: str = "public, max-age=30",
    verbose: bool = True,
) -> None:
    """
    Upload JSON data to S3 with gzip compression.

    Args:
        data: Dictionary to upload as JSON
        bucket: S3 bucket name
        key: S3 object key
        aws_access_key: AWS access key ID
        aws_secret_key: AWS secret access key
        cache_control: Cache-Control header value
        verbose: Whether to print detailed upload info
    """
    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
        )

        # Serialize to JSON
        json_content = json.dumps(data, indent=2)

        # Gzip compress the content
        compressed_content = gzip.compress(json_content.encode('utf-8'))

        # Calculate compression ratio
        original_size = len(json_content.encode('utf-8'))
        compressed_size = len(compressed_content)
        ratio = (1 - compressed_size / original_size) * 100

        s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=compressed_content,
            ContentType='application/json',
            ContentEncoding='gzip',  # Critical: tells browser to decompress
            CacheControl=cache_control,
            # Note: Public access is controlled by bucket policy, not object ACL
        )

        if verbose:
            print(f"  Successfully uploaded to s3://{bucket}/{key}")
            print(f"  Original size: {original_size:,} bytes")
            print(f"  Compressed size: {compressed_size:,} bytes ({ratio:.1f}% reduction)")
            print(f"  Public URL: https://{bucket}.s3.amazonaws.com/{key}")

    except Exception as e:
        print(f"ERROR uploading to S3: {e}", file=sys.stderr)
        raise


def main():
    """Main execution function."""
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Get configuration from environment
    db_path = Path(os.getenv("DUCKDB_PATH", "/data/tree.duckdb"))
    bucket = get_env_or_exit("S3_BUCKET")
    key = os.getenv("S3_KEY", "water-level.json")
    aws_access_key = get_env_or_exit("AWS_ACCESS_KEY_ID")
    aws_secret_key = get_env_or_exit("AWS_SECRET_ACCESS_KEY")

    # Configuration
    minutes_of_data = int(os.getenv("MINUTES_OF_DATA", "10"))
    replay_delay = int(os.getenv("REPLAY_DELAY_SECONDS", "300"))
    upload_interval = int(os.getenv("UPLOAD_INTERVAL_SECONDS", "30"))

    print("=" * 60)
    print("🎄 Treelemetry Uploader")
    print("=" * 60)
    print(f"Database:        {db_path}")
    print(f"S3 Target:       s3://{bucket}/{key}")
    print(f"Upload Interval: {upload_interval} seconds")
    print(f"Data Window:     {minutes_of_data} minutes")
    print(f"Replay Delay:    {replay_delay} seconds")
    print(f"Compression:     gzip enabled")
    print("=" * 60)
    print()

    # Verify database exists
    if not db_path.exists():
        print(f"❌ ERROR: Database file not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    print(f"✓ Database file found")
    print(f"✓ Starting upload daemon...")
    print()

    upload_count = 0
    error_count = 0
    first_upload = True
    cached_analysis = None  # Cache analysis results to include in every upload

    while not shutdown_requested:
        try:
            upload_count += 1
            start_time = time.time()

            # Only log upload attempts for first upload or after errors
            if first_upload or error_count > 0:
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Upload #{upload_count}")

            # Query raw data (last 10 minutes)
            measurements = query_water_levels(db_path, minutes=minutes_of_data)

            if first_upload or error_count > 0:
                print(f"  Retrieved {len(measurements)} raw measurements")

            # Query aggregated data at different scales
            try:
                # 1-minute intervals for last hour
                agg_1m = query_aggregated_data(db_path, interval_minutes=1, lookback_hours=1)

                # 5-minute intervals for last 24 hours
                agg_5m = query_aggregated_data(db_path, interval_minutes=5, lookback_hours=24)

                # 1-hour intervals for all historical data
                agg_1h = query_aggregated_data(db_path, interval_minutes=60, lookback_hours=None)

                if first_upload or error_count > 0:
                    print(f"  Aggregated: 1m={len(agg_1m)} pts, 5m={len(agg_5m)} pts, 1h={len(agg_1h)} pts")

            except Exception as e:
                print(f"  Warning: Could not generate aggregates: {e}")
                agg_1m = agg_5m = agg_1h = None

            # Query YoLink sensor aggregated data
            yolink_1m = yolink_5m = yolink_1h = None
            try:
                # 1-minute intervals for last hour
                yolink_1m = query_yolink_aggregated_data(db_path, interval_minutes=1, lookback_hours=1)

                # 5-minute intervals for last 24 hours
                yolink_5m = query_yolink_aggregated_data(db_path, interval_minutes=5, lookback_hours=24)

                # 1-hour intervals for all historical data
                yolink_1h = query_yolink_aggregated_data(db_path, interval_minutes=60, lookback_hours=None)

                if first_upload or error_count > 0:
                    air_1m = len(yolink_1m.get("air", []))
                    water_1m = len(yolink_1m.get("water", []))
                    air_5m = len(yolink_5m.get("air", []))
                    water_5m = len(yolink_5m.get("water", []))
                    air_1h = len(yolink_1h.get("air", []))
                    water_1h = len(yolink_1h.get("water", []))
                    if air_1m or water_1m or air_5m or water_5m or air_1h or water_1h:
                        print(f"  YoLink: air(1m={air_1m}, 5m={air_5m}, 1h={air_1h}), water(1m={water_1m}, 5m={water_5m}, 1h={water_1h})")

            except Exception as e:
                print(f"  Warning: Could not generate YoLink aggregates: {e}")

            # Perform segment analysis (expensive, so only periodically)
            # But always use cached results in JSON output
            if first_upload or (upload_count % 10 == 0):  # Every 10th upload
                try:
                    analysis = analyze_water_level_segments(db_path)
                    if analysis:
                        cached_analysis = analysis  # Update cache
                        if first_upload or error_count > 0:
                            seg_count = len(analysis.get("segments", []))
                            pred = analysis.get("current_prediction")
                            print(f"  Analysis: {seg_count} segments detected")
                            if pred:
                                print(f"  Current slope: {pred['slope_mm_per_hr']:.3f} mm/hr")
                                print(f"  Time to refill: {pred['time_to_50mm_hours']:.1f} hours")
                except Exception as e:
                    print(f"  Warning: Could not perform analysis: {e}")
                    import traceback
                    traceback.print_exc()

            # Create JSON structure with all data
            output_data = create_json_output(
                measurements,
                aggregates_1m=agg_1m,
                aggregates_5m=agg_5m,
                aggregates_1h=agg_1h,
                analysis=cached_analysis,  # Always use cached analysis
                yolink_1m=yolink_1m,
                yolink_5m=yolink_5m,
                yolink_1h=yolink_1h,
                replay_delay=replay_delay,
            )

            # Upload to S3 (verbose only on first upload)
            upload_to_s3(
                data=output_data,
                bucket=bucket,
                key=key,
                aws_access_key=aws_access_key,
                aws_secret_key=aws_secret_key,
                verbose=first_upload or error_count > 0,
            )

            elapsed = time.time() - start_time

            if first_upload:
                print(f"  ✓ Upload complete in {elapsed:.2f}s")
                print()
                print("✅ First upload successful!")
                print("   Daemon is now running. Uploads will continue silently.")
                print("   Press Ctrl+C or send SIGTERM to stop.")
                print()
                first_upload = False
            elif error_count > 0:
                print(f"  ✓ Upload recovered in {elapsed:.2f}s")
                print()

            # Reset error count on successful upload
            error_count = 0

        except KeyboardInterrupt:
            # Handle Ctrl+C gracefully
            break

        except Exception as e:
            error_count += 1
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✗ ERROR: {e}", file=sys.stderr)

            # If we have too many consecutive errors, bail out
            if error_count >= 10:
                print(f"❌ ERROR: Too many consecutive failures ({error_count}), exiting", file=sys.stderr)
                sys.exit(1)

            # On error, wait a bit before retrying
            print(f"  Waiting {upload_interval} seconds before retry...")

        # Sleep until next upload (unless shutdown requested)
        if not shutdown_requested:
            time.sleep(upload_interval)

    print()
    print("=" * 60)
    print("🎄 Treelemetry Uploader Stopped")
    print("=" * 60)
    print(f"Total uploads: {upload_count}")
    print(f"Final status:  {'✓ Clean shutdown' if error_count == 0 else f'✗ {error_count} errors'}")
    print("=" * 60)


if __name__ == "__main__":
    main()

