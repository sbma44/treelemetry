"""S3 upload functionality for JSON data."""

import gzip
import json
import logging
import math
from datetime import datetime, timezone
from typing import Any

import boto3

logger = logging.getLogger(__name__)


def calculate_stats(measurements: list[dict[str, Any]]) -> dict[str, float]:
    """Calculate statistics from measurements.

    Args:
        measurements: List of measurement dictionaries

    Returns:
        Dictionary with min_level, max_level, avg_level, stddev, and count
    """
    if not measurements:
        return {}

    levels = [
        m["water_level_mm"]
        for m in measurements
        if m["water_level_mm"] is not None
    ]

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


def create_json_output(
    measurements: list[dict[str, Any]],
    season_start: str,
    season_end: str,
    is_in_season: bool,
    aggregates_1m: list[dict[str, Any]] | None = None,
    aggregates_5m: list[dict[str, Any]] | None = None,
    aggregates_1h: list[dict[str, Any]] | None = None,
    analysis: dict[str, Any] | None = None,
    yolink_1m: dict[str, list[dict[str, Any]]] | None = None,
    yolink_5m: dict[str, list[dict[str, Any]]] | None = None,
    yolink_1h: dict[str, list[dict[str, Any]]] | None = None,
    replay_delay: int = 300,
) -> dict[str, Any]:
    """Create the JSON structure to upload.

    Args:
        measurements: List of raw measurement dictionaries (last 10 minutes)
        season_start: Season start date (ISO format)
        season_end: Season end date (ISO format)
        is_in_season: Whether currently in season
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
        "season": {
            "start": season_start,
            "end": season_end,
            "is_active": is_in_season,
        },
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

    def add_yolink_interval(
        key: str,
        data: dict[str, list] | None,
        interval_minutes: int,
        lookback_hours: int | None,
    ):
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
    data: dict[str, Any],
    bucket: str,
    key: str,
    aws_access_key: str,
    aws_secret_key: str,
    cache_control: str = "public, max-age=30",
    verbose: bool = True,
) -> None:
    """Upload JSON data to S3 with gzip compression.

    Args:
        data: Dictionary to upload as JSON
        bucket: S3 bucket name
        key: S3 object key
        aws_access_key: AWS access key ID
        aws_secret_key: AWS secret access key
        cache_control: Cache-Control header value
        verbose: Whether to print detailed upload info

    Raises:
        Exception: If upload fails
    """
    try:
        s3_client = boto3.client(
            "s3",
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
        )

        # Serialize to JSON
        json_content = json.dumps(data, indent=2)

        # Gzip compress the content
        compressed_content = gzip.compress(json_content.encode("utf-8"))

        # Calculate compression ratio
        original_size = len(json_content.encode("utf-8"))
        compressed_size = len(compressed_content)
        ratio = (1 - compressed_size / original_size) * 100

        s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=compressed_content,
            ContentType="application/json",
            ContentEncoding="gzip",  # Critical: tells browser to decompress
            CacheControl=cache_control,
            # Note: Public access is controlled by bucket policy, not object ACL
        )

        if verbose:
            logger.info(f"Successfully uploaded to s3://{bucket}/{key}")
            logger.info(f"Original size: {original_size:,} bytes")
            logger.info(
                f"Compressed size: {compressed_size:,} bytes ({ratio:.1f}% reduction)"
            )
            logger.info(f"Public URL: https://{bucket}.s3.amazonaws.com/{key}")

    except Exception as e:
        logger.error(f"ERROR uploading to S3: {e}")
        raise


