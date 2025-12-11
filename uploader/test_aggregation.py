#!/usr/bin/env python3
"""
Test script to verify the aggregation functionality and compression efficiency.
"""
import gzip
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from uploader import (
    query_water_levels,
    query_aggregated_data,
    create_json_output,
    calculate_stats,
)


def format_bytes(size):
    """Format bytes to human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"


def test_aggregation(db_path: str = "tree.duckdb"):
    """Test aggregation and report statistics."""
    db_path = Path(db_path)

    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        print("Run: uv run python sample_data.py")
        return

    print("=" * 70)
    print("🎄 Testing Treelemetry Aggregation")
    print("=" * 70)
    print()

    # Query raw measurements
    print("📊 Querying data...")
    measurements = query_water_levels(db_path, minutes=10)
    print(f"  Raw measurements (10 min): {len(measurements)} points")

    # Query aggregates
    agg_1m = query_aggregated_data(db_path, interval_minutes=1, lookback_hours=1)
    print(f"  1-minute aggregates (1 hour): {len(agg_1m)} points")

    agg_5m = query_aggregated_data(db_path, interval_minutes=5, lookback_hours=24)
    print(f"  5-minute aggregates (24 hours): {len(agg_5m)} points")

    agg_1h = query_aggregated_data(db_path, interval_minutes=60, lookback_hours=None)
    print(f"  1-hour aggregates (all time): {len(agg_1h)} points")
    print()

    # Create JSON output
    print("📦 Creating JSON output...")
    output_data = create_json_output(
        measurements,
        aggregates_1m=agg_1m,
        aggregates_5m=agg_5m,
        aggregates_1h=agg_1h,
        replay_delay=300,
    )

    # Serialize and compress
    json_content = json.dumps(output_data, indent=2)
    json_content_compact = json.dumps(output_data, separators=(',', ':'))
    compressed_content = gzip.compress(json_content_compact.encode('utf-8'))

    # Calculate sizes
    pretty_size = len(json_content.encode('utf-8'))
    compact_size = len(json_content_compact.encode('utf-8'))
    compressed_size = len(compressed_content)

    print()
    print("=" * 70)
    print("📏 Size Analysis")
    print("=" * 70)
    print(f"  Pretty JSON:      {format_bytes(pretty_size):>12}")
    print(f"  Compact JSON:     {format_bytes(compact_size):>12} ({compact_size/pretty_size*100:.1f}% of pretty)")
    print(f"  Gzipped:          {format_bytes(compressed_size):>12} ({compressed_size/compact_size*100:.1f}% of compact)")
    print()
    print(f"  Compression ratio: {(1 - compressed_size/pretty_size)*100:.1f}% reduction from pretty")
    print(f"                     {(1 - compressed_size/compact_size)*100:.1f}% reduction from compact")
    print()

    # Show data structure
    print("=" * 70)
    print("📋 Data Structure Summary")
    print("=" * 70)
    print(f"  Fields in output:")
    for key in output_data.keys():
        if key == "measurements":
            print(f"    • {key}: {len(output_data[key])} items")
        elif key.startswith("agg_"):
            data = output_data[key]
            print(f"    • {key}: {data['interval_minutes']}min intervals, {len(data['data'])} points")
            if data['data']:
                sample = data['data'][0]
                print(f"        Keys per point: {list(sample.keys())}")
        elif key == "stats":
            print(f"    • {key}: {list(output_data[key].keys())}")
        else:
            print(f"    • {key}: {output_data[key]}")
    print()

    # Show sample aggregated data
    if agg_1m:
        print("=" * 70)
        print("📊 Sample Aggregated Data (1-minute intervals)")
        print("=" * 70)
        print("  First 3 points:")
        for i, point in enumerate(agg_1m[:3]):
            print(f"    {i+1}. {point}")
        print()
        if len(agg_1m) > 3:
            print(f"  ... ({len(agg_1m) - 3} more points)")
            print()

    # Mobile performance estimate
    print("=" * 70)
    print("📱 Mobile Performance Estimate")
    print("=" * 70)
    print(f"  Download size: {format_bytes(compressed_size)}")
    print(f"  Parse size: {format_bytes(compact_size)}")
    print(f"  Total data points: {len(measurements) + len(agg_1m) + len(agg_5m) + len(agg_1h)}")

    # Estimate network time (rough estimates)
    # 3G: ~1 Mbps, 4G: ~10 Mbps, 5G: ~100 Mbps
    download_3g = (compressed_size * 8) / (1_000_000)  # seconds
    download_4g = (compressed_size * 8) / (10_000_000)
    download_5g = (compressed_size * 8) / (100_000_000)

    print(f"  Download time (estimated):")
    print(f"    3G:  {download_3g:.2f}s")
    print(f"    4G:  {download_4g:.3f}s")
    print(f"    5G:  {download_5g:.4f}s")
    print()

    print("=" * 70)
    print("✅ Test Complete!")
    print("=" * 70)

    # Save sample output
    sample_path = Path("sample_output.json")
    with open(sample_path, 'w') as f:
        f.write(json_content)
    print(f"\n💾 Sample output saved to: {sample_path}")

    sample_gz_path = Path("sample_output.json.gz")
    with open(sample_gz_path, 'wb') as f:
        f.write(compressed_content)
    print(f"💾 Compressed output saved to: {sample_gz_path}")


if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else "tree.duckdb"
    test_aggregation(db_path)


