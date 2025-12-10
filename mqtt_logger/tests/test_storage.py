"""Tests for storage module."""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from src.mqtt_logger.storage import MessageStore


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        yield db_path


@pytest.fixture
def message_store(temp_db):
    """Create a MessageStore instance for testing."""
    store = MessageStore(temp_db, batch_size=5, flush_interval=1)
    yield store
    store.close()


def test_create_table(message_store):
    """Test creating a table."""
    message_store.create_table("test_sensors")
    
    # Verify table exists by querying it
    result = message_store.query("test_sensors")
    assert result == []


def test_create_table_invalid_name(message_store):
    """Test creating a table with invalid name."""
    with pytest.raises(ValueError, match="Invalid table name"):
        message_store.create_table("test; DROP TABLE users;")


def test_insert_and_query_message(message_store):
    """Test inserting and querying messages."""
    message_store.create_table("test_table")
    
    # Insert a message
    message_store.insert_message(
        "test_table",
        "sensors/temp/1",
        b"23.5",
        qos=1,
        retain=False,
    )
    
    # Force flush
    message_store.flush("test_table")
    
    # Query messages
    messages = message_store.query("test_table")
    assert len(messages) == 1
    assert messages[0]["topic"] == "sensors/temp/1"
    assert messages[0]["payload"] == "23.5"
    assert messages[0]["qos"] == 1
    assert messages[0]["retain"] is False


def test_batch_insert(message_store):
    """Test batch insertion."""
    message_store.create_table("test_batch")
    
    # Insert messages (batch_size is 5)
    for i in range(3):
        message_store.insert_message(
            "test_batch",
            f"sensors/temp/{i}",
            f"{20 + i}".encode(),
            qos=0,
        )
    
    # Should not be flushed yet (batch_size=5)
    messages = message_store.query("test_batch")
    assert len(messages) == 0
    
    # Insert 2 more to trigger batch flush
    for i in range(3, 5):
        message_store.insert_message(
            "test_batch",
            f"sensors/temp/{i}",
            f"{20 + i}".encode(),
            qos=0,
        )
    
    # Should be flushed now
    messages = message_store.query("test_batch")
    assert len(messages) == 5


def test_non_utf8_payload(message_store):
    """Test handling of non-UTF-8 payload."""
    message_store.create_table("test_binary")
    
    # Insert binary data that's not valid UTF-8
    binary_data = b"\x80\x81\x82\x83"
    message_store.insert_message(
        "test_binary",
        "binary/test",
        binary_data,
        qos=0,
    )
    message_store.flush("test_binary")
    
    # Should be stored as hex
    messages = message_store.query("test_binary")
    assert len(messages) == 1
    assert messages[0]["payload"] == binary_data.hex()


def test_query_with_time_filter(message_store):
    """Test querying with time filters."""
    message_store.create_table("test_time")
    
    # Insert messages
    for i in range(5):
        message_store.insert_message(
            "test_time",
            f"test/{i}",
            str(i).encode(),
            qos=0,
        )
    message_store.flush("test_time")
    
    # Query with time range
    now = datetime.now()
    start_time = now - timedelta(minutes=1)
    end_time = now + timedelta(minutes=1)
    
    messages = message_store.query(
        "test_time",
        start_time=start_time,
        end_time=end_time,
    )
    assert len(messages) == 5


def test_query_with_topic_filter(message_store):
    """Test querying with topic filter."""
    message_store.create_table("test_filter")
    
    # Insert messages with different topics
    topics = ["sensors/temp", "sensors/humidity", "devices/status"]
    for topic in topics:
        message_store.insert_message("test_filter", topic, b"data", qos=0)
    message_store.flush("test_filter")
    
    # Query with topic filter
    messages = message_store.query("test_filter", topic_filter="sensors/%")
    assert len(messages) == 2
    assert all("sensors/" in msg["topic"] for msg in messages)


def test_query_with_limit(message_store):
    """Test querying with limit."""
    message_store.create_table("test_limit")
    
    # Insert 10 messages
    for i in range(10):
        message_store.insert_message(
            "test_limit",
            "test/topic",
            str(i).encode(),
            qos=0,
        )
    message_store.flush("test_limit")
    
    # Query with limit
    messages = message_store.query("test_limit", limit=5)
    assert len(messages) == 5


def test_get_stats(message_store):
    """Test getting statistics."""
    message_store.create_table("test_stats")
    
    # Empty table
    stats = message_store.get_stats("test_stats")
    assert stats["count"] == 0
    
    # Insert messages
    for i in range(10):
        message_store.insert_message(
            "test_stats",
            f"topic/{i % 3}",
            str(i).encode(),
            qos=0,
        )
    message_store.flush("test_stats")
    
    # Check stats
    stats = message_store.get_stats("test_stats")
    assert stats["count"] == 10
    assert stats["unique_topics"] == 3
    assert "first_message" in stats
    assert "last_message" in stats


def test_flush_all_tables(message_store):
    """Test flushing all tables."""
    # Create multiple tables
    message_store.create_table("table1")
    message_store.create_table("table2")
    
    # Insert messages to both
    message_store.insert_message("table1", "test", b"data1", qos=0)
    message_store.insert_message("table2", "test", b"data2", qos=0)
    
    # Flush all
    message_store.flush()
    
    # Verify both are flushed
    assert len(message_store.query("table1")) == 1
    assert len(message_store.query("table2")) == 1


def test_close_flushes_pending(message_store):
    """Test that closing flushes pending messages."""
    message_store.create_table("test_close")
    
    # Insert messages (less than batch_size)
    message_store.insert_message("test_close", "test", b"data", qos=0)
    
    # Close (should flush)
    message_store.close()
    
    # Reopen and verify
    new_store = MessageStore(message_store.db_path)
    messages = new_store.query("test_close")
    assert len(messages) == 1
    new_store.close()


def test_query_invalid_table_name(message_store):
    """Test querying with invalid table name."""
    with pytest.raises(ValueError, match="Invalid table name"):
        message_store.query("test; DROP TABLE users;")


def test_stats_invalid_table_name(message_store):
    """Test getting stats with invalid table name."""
    with pytest.raises(ValueError, match="Invalid table name"):
        message_store.get_stats("test; DROP TABLE users;")

