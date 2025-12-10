"""DuckDB storage backend for MQTT messages."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import duckdb

logger = logging.getLogger(__name__)


class MessageStore:
    """DuckDB-backed storage for MQTT messages.

    Attributes:
        db_path: Path to the DuckDB database file
        batch_size: Number of messages to batch before writing
        flush_interval: Seconds between forced flushes

    Example:
        >>> store = MessageStore("data/mqtt.db", batch_size=50)
        >>> store.create_table("sensors")
        >>> store.insert_message("sensors", "sensor/temp", b"23.5", qos=1)
        >>> messages = store.query("sensors", limit=10)
    """

    def __init__(
        self,
        db_path: str | Path,
        batch_size: int = 100,
        flush_interval: int = 10,
    ):
        """Initialize the message store.

        Args:
            db_path: Path to the DuckDB database file
            batch_size: Number of messages to batch before writing
            flush_interval: Seconds between forced flushes
        """
        self.db_path = Path(db_path)
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self._batches: dict[str, list[dict[str, Any]]] = {}
        self._last_flush: dict[str, datetime] = {}

        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize connection
        self._conn = duckdb.connect(str(self.db_path))

        # Configure DuckDB for minimal disk writes (SD card friendly)
        # These settings prioritize memory caching over disk durability
        self._conn.execute("PRAGMA wal_autocheckpoint='1GB'")  # Delay WAL checkpoints
        self._conn.execute("PRAGMA checkpoint_threshold='1GB'")  # Large checkpoint threshold

        logger.info(f"Connected to DuckDB at {self.db_path} (SD card optimized)")

    def create_table(self, table_name: str) -> None:
        """Create a table for storing MQTT messages if it doesn't exist.

        Args:
            table_name: Name of the table to create

        The table schema includes:
        - id: Auto-incrementing integer primary key
        - timestamp: Message receipt timestamp
        - topic: MQTT topic
        - payload: Message payload (as text)
        - qos: Quality of Service level
        - retain: Whether message was retained
        """
        # Validate table name to prevent SQL injection
        if not table_name.replace("_", "").isalnum():
            raise ValueError(f"Invalid table name: {table_name}")

        # Create sequence for auto-incrementing IDs
        seq_name = f"{table_name}_id_seq"
        self._conn.execute(f"CREATE SEQUENCE IF NOT EXISTS {seq_name} START 1")

        query = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id INTEGER PRIMARY KEY DEFAULT nextval('{seq_name}'),
            timestamp TIMESTAMP NOT NULL,
            topic VARCHAR NOT NULL,
            payload VARCHAR,
            qos INTEGER,
            retain BOOLEAN
        )
        """

        self._conn.execute(query)
        self._conn.commit()

        # Create index on timestamp for efficient time-based queries
        index_query = f"""
        CREATE INDEX IF NOT EXISTS idx_{table_name}_timestamp
        ON {table_name}(timestamp)
        """
        self._conn.execute(index_query)
        self._conn.commit()

        # Initialize batch tracking
        if table_name not in self._batches:
            self._batches[table_name] = []
            self._last_flush[table_name] = datetime.now()

        logger.info(f"Table '{table_name}' ready")

    def insert_message(
        self,
        table_name: str,
        topic: str,
        payload: bytes,
        qos: int = 0,
        retain: bool = False,
    ) -> None:
        """Insert a message into the database (batched).

        Args:
            table_name: Target table name
            topic: MQTT topic
            payload: Message payload
            qos: Quality of Service level
            retain: Whether message was retained
        """
        # Decode payload to string (assuming UTF-8, with fallback)
        try:
            payload_str = payload.decode("utf-8")
        except UnicodeDecodeError:
            payload_str = payload.hex()
            logger.warning(f"Non-UTF-8 payload on {topic}, stored as hex")

        message = {
            "timestamp": datetime.now(),
            "topic": topic,
            "payload": payload_str,
            "qos": qos,
            "retain": retain,
        }

        self._batches[table_name].append(message)

        # Check if we should flush
        should_flush = (
            len(self._batches[table_name]) >= self.batch_size
            or (datetime.now() - self._last_flush[table_name]).total_seconds()
            >= self.flush_interval
        )

        if should_flush:
            self.flush(table_name)

    def flush(self, table_name: str | None = None) -> None:
        """Flush pending messages to the database.

        Args:
            table_name: Specific table to flush, or None to flush all
        """
        tables_to_flush = (
            [table_name] if table_name else list(self._batches.keys())
        )

        for tbl in tables_to_flush:
            if not self._batches.get(tbl):
                continue

            messages = self._batches[tbl]

            # Validate table name
            if not tbl.replace("_", "").isalnum():
                logger.error(f"Invalid table name: {tbl}")
                continue

            try:
                # Use DuckDB's efficient batch insert
                self._conn.executemany(
                    f"""
                    INSERT INTO {tbl} (timestamp, topic, payload, qos, retain)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            msg["timestamp"],
                            msg["topic"],
                            msg["payload"],
                            msg["qos"],
                            msg["retain"],
                        )
                        for msg in messages
                    ],
                )
                self._conn.commit()
                
                # Explicitly checkpoint to merge WAL into main database file
                # Without this, the WAL grows indefinitely due to our aggressive PRAGMA settings
                self._conn.execute("CHECKPOINT")

                logger.debug(
                    f"Flushed {len(messages)} messages to table '{tbl}'"
                )

                self._batches[tbl] = []
                self._last_flush[tbl] = datetime.now()

            except Exception as e:
                logger.error(f"Failed to flush messages to '{tbl}': {e}")

    def query(
        self,
        table_name: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        topic_filter: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Query messages from the database.

        Args:
            table_name: Table to query
            start_time: Optional start timestamp filter
            end_time: Optional end timestamp filter
            topic_filter: Optional topic pattern (SQL LIKE syntax)
            limit: Optional maximum number of results

        Returns:
            List of message dictionaries
        """
        # Validate table name
        if not table_name.replace("_", "").isalnum():
            raise ValueError(f"Invalid table name: {table_name}")

        query = f"SELECT * FROM {table_name} WHERE 1=1"
        params = []

        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time)

        if end_time:
            query += " AND timestamp <= ?"
            params.append(end_time)

        if topic_filter:
            query += " AND topic LIKE ?"
            params.append(topic_filter)

        query += " ORDER BY timestamp DESC"

        if limit:
            query += f" LIMIT {limit}"

        result = self._conn.execute(query, params).fetchall()

        # Convert to dictionaries
        columns = ["id", "timestamp", "topic", "payload", "qos", "retain"]
        return [dict(zip(columns, row)) for row in result]

    def get_stats(self, table_name: str) -> dict[str, Any]:
        """Get statistics for a table.

        Args:
            table_name: Table to get stats for

        Returns:
            Dictionary with count, first_message, last_message, etc.
        """
        # Validate table name
        if not table_name.replace("_", "").isalnum():
            raise ValueError(f"Invalid table name: {table_name}")

        stats = {}

        # Get count
        result = self._conn.execute(
            f"SELECT COUNT(*) FROM {table_name}"
        ).fetchone()
        stats["count"] = result[0] if result else 0

        if stats["count"] > 0:
            # Get first and last message times
            result = self._conn.execute(
                f"""
                SELECT MIN(timestamp) as first, MAX(timestamp) as last
                FROM {table_name}
                """
            ).fetchone()
            stats["first_message"] = result[0]
            stats["last_message"] = result[1]

            # Get topic count
            result = self._conn.execute(
                f"SELECT COUNT(DISTINCT topic) FROM {table_name}"
            ).fetchone()
            stats["unique_topics"] = result[0]

        return stats

    def close(self) -> None:
        """Close the database connection, flushing any pending writes."""
        # Flush all pending messages
        for table_name in list(self._batches.keys()):
            self.flush(table_name)

        # Final checkpoint to ensure WAL is fully merged into main database
        try:
            self._conn.execute("CHECKPOINT")
            logger.info("Final checkpoint completed - WAL merged to main database")
        except Exception as e:
            logger.warning(f"Final checkpoint failed: {e}")

        self._conn.close()
        logger.info("Database connection closed")

