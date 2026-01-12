#!/usr/bin/env python3
"""Merge two DuckDB databases into a single output database.

This tool combines historical data from an old database with a new database,
deduplicating records based on timestamp and topic/device_id.

Usage:
    python merge_databases.py old_db.duckdb new_db.duckdb output_db.duckdb

Example:
    # Merge old mqtt_logger data with new data_sleigh data
    python merge_databases.py \
        /old/mqtt_logs.db \
        /new/mqtt_logs.db \
        /merged/mqtt_logs.db
"""

import argparse
import logging
import sys
from pathlib import Path

import duckdb

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def get_tables(conn: duckdb.DuckDBPyConnection) -> list[str]:
    """Get list of tables in the database."""
    result = conn.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
    ).fetchall()
    return [row[0] for row in result]


def get_table_columns(conn: duckdb.DuckDBPyConnection, table_name: str) -> list[str]:
    """Get column names for a table."""
    result = conn.execute(f"PRAGMA table_info('{table_name}')").fetchall()
    return [row[1] for row in result]


def is_yolink_table(table_name: str, columns: list[str]) -> bool:
    """Check if table is a YoLink sensor table based on name or columns.

    A table is considered YoLink if:
    - The name contains 'yolink' (canonical naming), OR
    - It has device_id and device_type columns (correct schema)
    """
    # Check by name first (handles cases where old schema was wrong)
    if "yolink" in table_name.lower():
        return True
    # Fall back to column-based detection
    return "device_id" in columns and "device_type" in columns


def merge_tables(
    old_conn: duckdb.DuckDBPyConnection,
    new_conn: duckdb.DuckDBPyConnection,
    out_conn: duckdb.DuckDBPyConnection,
    table_name: str,
) -> tuple[int, int, int]:
    """Merge a table from old and new databases into output.

    Returns:
        Tuple of (old_count, new_count, merged_count)
    """
    old_tables = get_tables(old_conn)
    new_tables = get_tables(new_conn)

    if table_name not in old_tables and table_name not in new_tables:
        logger.warning(f"Table {table_name} not found in either database")
        return 0, 0, 0

    # Get columns from each database separately
    old_columns = get_table_columns(old_conn, table_name) if table_name in old_tables else []
    new_columns = get_table_columns(new_conn, table_name) if table_name in new_tables else []

    # Determine table type based on table name and columns
    all_columns = old_columns or new_columns
    is_yolink = is_yolink_table(table_name, all_columns)

    # Define the canonical schema for each table type
    if is_yolink:
        canonical_columns = [
            "timestamp", "topic", "device_id", "device_type",
            "temperature", "humidity", "battery", "signal", "raw_json"
        ]
        seq_name = f"{table_name}_id_seq"
        out_conn.execute(f"CREATE SEQUENCE IF NOT EXISTS {seq_name} START 1")
        out_conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                id INTEGER PRIMARY KEY DEFAULT nextval('{seq_name}'),
                timestamp TIMESTAMP NOT NULL,
                topic VARCHAR NOT NULL,
                device_id VARCHAR NOT NULL,
                device_type VARCHAR NOT NULL,
                temperature DOUBLE,
                humidity DOUBLE,
                battery INTEGER,
                signal INTEGER,
                raw_json VARCHAR
            )
        """)
    else:
        canonical_columns = ["timestamp", "topic", "payload", "qos", "retain"]
        seq_name = f"{table_name}_id_seq"
        out_conn.execute(f"CREATE SEQUENCE IF NOT EXISTS {seq_name} START 1")
        out_conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                id INTEGER PRIMARY KEY DEFAULT nextval('{seq_name}'),
                timestamp TIMESTAMP NOT NULL,
                topic VARCHAR NOT NULL,
                payload VARCHAR,
                qos INTEGER,
                retain BOOLEAN
            )
        """)

    out_conn.commit()
    canonical_str = ", ".join(canonical_columns)
    placeholders = ", ".join(["?" for _ in canonical_columns])

    old_count = 0
    new_count = 0

    def copy_from_db(
        source_conn: duckdb.DuckDBPyConnection,
        source_columns: list[str],
        deduplicate: bool = False,
    ) -> tuple[int, int, int]:
        """Copy records from source to output, optionally deduplicating."""
        # Check if source has required columns for this table type
        source_cols_set = set(source_columns)

        if is_yolink:
            # YoLink tables need device_id and device_type to be useful
            required_cols = {"device_id", "device_type", "timestamp"}
            if not required_cols.issubset(source_cols_set):
                logger.warning(
                    f"  Skipping source - incompatible schema "
                    f"(missing: {required_cols - source_cols_set})"
                )
                return 0, 0, 0

        # Build column mapping - use source column if it exists, else NULL
        select_parts = []
        for col in canonical_columns:
            if col in source_cols_set:
                select_parts.append(col)
            else:
                select_parts.append(f"NULL as {col}")
        select_str = ", ".join(select_parts)

        data = source_conn.execute(f"SELECT {select_str} FROM {table_name}").fetchall()
        total = len(data)

        if not deduplicate:
            out_conn.executemany(
                f"INSERT INTO {table_name} ({canonical_str}) VALUES ({placeholders})",
                data
            )
            out_conn.commit()
            return total, 0, total

        # Deduplicate against existing records
        inserted = 0
        skipped = 0

        for row in data:
            row_dict = dict(zip(canonical_columns, row))

            if is_yolink:
                check_result = out_conn.execute(
                    f"""SELECT 1 FROM {table_name}
                        WHERE timestamp = ? AND device_id = ? AND device_type = ?
                        LIMIT 1""",
                    [row_dict["timestamp"], row_dict["device_id"], row_dict["device_type"]]
                ).fetchone()
            else:
                check_result = out_conn.execute(
                    f"""SELECT 1 FROM {table_name}
                        WHERE timestamp = ? AND topic = ?
                        LIMIT 1""",
                    [row_dict["timestamp"], row_dict["topic"]]
                ).fetchone()

            if check_result is None:
                out_conn.execute(
                    f"INSERT INTO {table_name} ({canonical_str}) VALUES ({placeholders})",
                    row
                )
                inserted += 1
            else:
                skipped += 1

        out_conn.commit()
        return total, inserted, skipped

    # Insert from old database (no deduplication needed - it's first)
    if table_name in old_tables and old_columns:
        result = old_conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
        old_count = result[0] if result else 0

        if old_count > 0:
            logger.info(f"  Copying {old_count} records from old database...")
            copy_from_db(old_conn, old_columns, deduplicate=False)

    # Insert from new database with deduplication
    if table_name in new_tables and new_columns:
        result = new_conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
        new_count = result[0] if result else 0

        if new_count > 0:
            logger.info(f"  Merging {new_count} records from new database (deduplicating)...")
            _, inserted, skipped = copy_from_db(new_conn, new_columns, deduplicate=True)
            logger.info(f"  Inserted {inserted} new records, skipped {skipped} duplicates")

    # Get final count
    result = out_conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
    merged_count = result[0] if result else 0

    # Create indexes
    out_conn.execute(f"""
        CREATE INDEX IF NOT EXISTS idx_{table_name}_timestamp
        ON {table_name}(timestamp)
    """)

    if is_yolink:
        out_conn.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_{table_name}_device
            ON {table_name}(device_id, device_type)
        """)

    out_conn.commit()

    return old_count, new_count, merged_count


def merge_databases(old_path: Path, new_path: Path, output_path: Path) -> None:
    """Merge two DuckDB databases into a single output database.

    Args:
        old_path: Path to the old/historical database
        new_path: Path to the new database
        output_path: Path for the merged output database
    """
    logger.info(f"Old database: {old_path}")
    logger.info(f"New database: {new_path}")
    logger.info(f"Output database: {output_path}")

    # Verify input files exist
    if not old_path.exists():
        raise FileNotFoundError(f"Old database not found: {old_path}")
    if not new_path.exists():
        raise FileNotFoundError(f"New database not found: {new_path}")

    # Remove output file if it exists
    if output_path.exists():
        logger.warning(f"Removing existing output file: {output_path}")
        output_path.unlink()

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Open connections
    old_conn = duckdb.connect(str(old_path), read_only=True)
    new_conn = duckdb.connect(str(new_path), read_only=True)
    out_conn = duckdb.connect(str(output_path))

    try:
        # Get all tables from both databases
        old_tables = set(get_tables(old_conn))
        new_tables = set(get_tables(new_conn))
        all_tables = old_tables | new_tables

        # Filter out internal/system tables
        all_tables = {t for t in all_tables if not t.startswith("_")}

        logger.info(f"Tables in old database: {sorted(old_tables)}")
        logger.info(f"Tables in new database: {sorted(new_tables)}")
        logger.info(f"Tables to merge: {sorted(all_tables)}")

        # Merge each table
        for table_name in sorted(all_tables):
            logger.info(f"\nMerging table: {table_name}")
            old_count, new_count, merged_count = merge_tables(
                old_conn, new_conn, out_conn, table_name
            )
            logger.info(
                f"  Result: {old_count} (old) + {new_count} (new) -> {merged_count} (merged)"
            )

        # Final checkpoint
        out_conn.execute("CHECKPOINT")
        logger.info("\n✅ Merge complete!")

        # Print final stats
        logger.info("\nFinal database statistics:")
        for table_name in sorted(all_tables):
            result = out_conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
            count = result[0] if result else 0

            result = out_conn.execute(
                f"SELECT MIN(timestamp), MAX(timestamp) FROM {table_name}"
            ).fetchone()
            if result and result[0]:
                logger.info(
                    f"  {table_name}: {count} records "
                    f"({result[0]} to {result[1]})"
                )
            else:
                logger.info(f"  {table_name}: {count} records")

    finally:
        old_conn.close()
        new_conn.close()
        out_conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Merge two DuckDB databases into a single output database.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Merge old and new databases
    python merge_databases.py old.db new.db merged.db

    # Typical usage with data_sleigh
    docker stop data-sleigh
    python merge_databases.py \\
        /path/to/old/mqtt_logs.db \\
        /path/to/new/mqtt_logs.db \\
        /path/to/merged/mqtt_logs.db
    mv /path/to/merged/mqtt_logs.db /path/to/new/mqtt_logs.db
    docker start data-sleigh
        """,
    )

    parser.add_argument(
        "old_db",
        type=Path,
        help="Path to the old/historical database",
    )
    parser.add_argument(
        "new_db",
        type=Path,
        help="Path to the new database",
    )
    parser.add_argument(
        "output_db",
        type=Path,
        help="Path for the merged output database",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        merge_databases(args.old_db, args.new_db, args.output_db)
    except Exception as e:
        logger.error(f"Merge failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

