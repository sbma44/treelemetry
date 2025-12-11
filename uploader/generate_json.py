#!/usr/bin/env python3
"""
Generate JSON output from a DuckDB database file.

This script produces the same JSON that would normally be uploaded to S3,
useful for testing and debugging.

Usage:
    python generate_json.py <duckdb_file> [output_file]

Examples:
    python generate_json.py mqtt_logs.db
    python generate_json.py mqtt_logs.db output.json
    python generate_json.py /path/to/tree.duckdb water-level.json
"""
import argparse
import json
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from uploader import (
    analyze_water_level_segments,
    create_json_output,
    query_aggregated_data,
    query_water_levels,
    query_yolink_aggregated_data,
)


def main():
    parser = argparse.ArgumentParser(
        description="Generate JSON output from a DuckDB database file"
    )
    parser.add_argument(
        "db_path",
        type=Path,
        help="Path to the DuckDB database file",
    )
    parser.add_argument(
        "output",
        type=Path,
        nargs="?",
        default=None,
        help="Output JSON file path (default: stdout)",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        default=True,
        help="Pretty-print JSON output (default: True)",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Output compact JSON (no indentation)",
    )
    parser.add_argument(
        "--no-analysis",
        action="store_true",
        help="Skip segment analysis (faster)",
    )
    parser.add_argument(
        "--minutes",
        type=int,
        default=10,
        help="Minutes of raw data to include (default: 10)",
    )
    parser.add_argument(
        "--replay-delay",
        type=int,
        default=300,
        help="Replay delay in seconds (default: 300)",
    )

    args = parser.parse_args()

    # Validate input file
    if not args.db_path.exists():
        print(f"ERROR: Database file not found: {args.db_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Reading from: {args.db_path}", file=sys.stderr)

    # Query raw measurements
    print("  Querying raw measurements...", file=sys.stderr)
    measurements = query_water_levels(args.db_path, minutes=args.minutes)
    print(f"  Retrieved {len(measurements)} raw measurements", file=sys.stderr)

    # Query water level aggregates
    print("  Querying water level aggregates...", file=sys.stderr)
    try:
        agg_1m = query_aggregated_data(args.db_path, interval_minutes=1, lookback_hours=1)
        agg_5m = query_aggregated_data(args.db_path, interval_minutes=5, lookback_hours=24)
        agg_1h = query_aggregated_data(args.db_path, interval_minutes=60, lookback_hours=None)
        print(f"  Water level: 1m={len(agg_1m)} pts, 5m={len(agg_5m)} pts, 1h={len(agg_1h)} pts", file=sys.stderr)
    except Exception as e:
        print(f"  Warning: Could not generate water level aggregates: {e}", file=sys.stderr)
        agg_1m = agg_5m = agg_1h = None

    # Query YoLink sensor aggregates
    print("  Querying YoLink sensor aggregates...", file=sys.stderr)
    try:
        yolink_1m = query_yolink_aggregated_data(args.db_path, interval_minutes=1, lookback_hours=1)
        yolink_5m = query_yolink_aggregated_data(args.db_path, interval_minutes=5, lookback_hours=24)
        yolink_1h = query_yolink_aggregated_data(args.db_path, interval_minutes=60, lookback_hours=None)

        air_1m = len(yolink_1m.get("air", []))
        water_1m = len(yolink_1m.get("water", []))
        air_5m = len(yolink_5m.get("air", []))
        water_5m = len(yolink_5m.get("water", []))
        air_1h = len(yolink_1h.get("air", []))
        water_1h = len(yolink_1h.get("water", []))

        if air_1m or water_1m or air_5m or water_5m or air_1h or water_1h:
            print(f"  YoLink: air(1m={air_1m}, 5m={air_5m}, 1h={air_1h}), water(1m={water_1m}, 5m={water_5m}, 1h={water_1h})", file=sys.stderr)
        else:
            print("  YoLink: no data found", file=sys.stderr)
    except Exception as e:
        print(f"  Warning: Could not generate YoLink aggregates: {e}", file=sys.stderr)
        yolink_1m = yolink_5m = yolink_1h = None

    # Perform segment analysis
    analysis = None
    if not args.no_analysis:
        print("  Running segment analysis...", file=sys.stderr)
        try:
            analysis = analyze_water_level_segments(args.db_path)
            if analysis:
                seg_count = len(analysis.get("segments", []))
                pred = analysis.get("current_prediction")
                print(f"  Analysis: {seg_count} segments detected", file=sys.stderr)
                if pred:
                    print(f"  Current slope: {pred['slope_mm_per_hr']:.3f} mm/hr", file=sys.stderr)
                    print(f"  Time to refill: {pred['time_to_50mm_hours']:.1f} hours", file=sys.stderr)
            else:
                print("  Analysis: insufficient data", file=sys.stderr)
        except Exception as e:
            print(f"  Warning: Could not perform analysis: {e}", file=sys.stderr)

    # Create JSON output
    output_data = create_json_output(
        measurements,
        aggregates_1m=agg_1m,
        aggregates_5m=agg_5m,
        aggregates_1h=agg_1h,
        analysis=analysis,
        yolink_1m=yolink_1m,
        yolink_5m=yolink_5m,
        yolink_1h=yolink_1h,
        replay_delay=args.replay_delay,
    )

    # Format JSON
    indent = None if args.compact else 2
    json_output = json.dumps(output_data, indent=indent)

    # Write output
    if args.output:
        args.output.write_text(json_output)
        print(f"  Written to: {args.output}", file=sys.stderr)
        print(f"  Size: {len(json_output):,} bytes", file=sys.stderr)
    else:
        print(json_output)

    print("Done!", file=sys.stderr)


if __name__ == "__main__":
    main()
