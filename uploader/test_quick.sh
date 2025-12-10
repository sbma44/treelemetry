#!/bin/bash
# Quick test script to verify the aggregation system is working

set -e

echo "=========================================="
echo "🎄 Treelemetry Aggregation Quick Test"
echo "=========================================="
echo ""

# Check if database exists
if [ ! -f "tree.duckdb" ]; then
    echo "📦 Generating sample data (7 days)..."
    uv run python sample_data.py tree.duckdb 7
    echo ""
fi

# Run aggregation test
echo "🧪 Testing aggregation and compression..."
uv run python test_aggregation.py tree.duckdb

echo ""
echo "=========================================="
echo "✅ Test complete!"
echo "=========================================="
echo ""
echo "Files generated:"
echo "  - tree.duckdb (sample database)"
echo "  - sample_output.json (pretty formatted)"
echo "  - sample_output.json.gz (compressed)"
echo ""
echo "To clean up: rm tree.duckdb* sample_output.json*"


