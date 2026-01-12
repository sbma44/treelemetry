"""Tests for DuckDB storage."""

import pytest

from data_sleigh.storage import MessageStore


def test_create_mqtt_table(test_db_path):
    """Test creating a standard MQTT message table."""
    store = MessageStore(test_db_path)
    store.create_table("test_messages")

    # Check table exists
    tables = store.get_connection().execute("SHOW TABLES").fetchall()
    table_names = [t[0] for t in tables]
    assert "test_messages" in table_names

    store.close()


def test_create_yolink_table(test_db_path):
    """Test creating a YoLink sensor table with normalized schema."""
    store = MessageStore(test_db_path)
    store.create_yolink_table("yolink_sensors")

    # Check table exists
    tables = store.get_connection().execute("SHOW TABLES").fetchall()
    table_names = [t[0] for t in tables]
    assert "yolink_sensors" in table_names

    # Check schema has expected columns
    schema = store.get_connection().execute(
        "DESCRIBE yolink_sensors"
    ).fetchall()
    column_names = [row[0] for row in schema]

    expected_columns = [
        "id",
        "timestamp",
        "topic",
        "device_id",
        "device_type",
        "temperature",
        "humidity",
        "battery",
        "signal",
        "raw_json",
    ]
    for col in expected_columns:
        assert col in column_names

    store.close()


def test_insert_mqtt_message(test_db_path):
    """Test inserting MQTT messages."""
    store = MessageStore(test_db_path, batch_size=1)
    store.create_table("test_messages")

    # Insert a message
    store.insert_message(
        "test_messages",
        "test/topic",
        b"test payload",
        qos=1,
        retain=False,
    )

    # Query it back
    messages = store.query("test_messages", limit=10)
    assert len(messages) == 1
    assert messages[0]["topic"] == "test/topic"
    assert messages[0]["payload"] == "test payload"

    store.close()


def test_insert_yolink_message(test_db_path):
    """Test inserting YoLink sensor data with normalized schema."""
    store = MessageStore(test_db_path, batch_size=1)
    store.create_yolink_table("yolink_sensors")

    # Insert a YoLink message
    raw_data = {
        "event": "THSensor.Report",
        "deviceId": "test123",
        "data": {"temperature": 72.5, "humidity": 45.0},
    }

    store.insert_yolink_message(
        device_type="air",
        device_id="test123",
        temperature=72.5,
        humidity=45.0,
        battery=100,
        signal=-50,
        raw_data=raw_data,
        table_name="yolink_sensors",
    )

    # Query it back
    results = store.get_connection().execute(
        "SELECT * FROM yolink_sensors"
    ).fetchall()

    assert len(results) == 1
    row = results[0]
    # id, timestamp, topic, device_id, device_type, temperature, humidity, battery, signal, raw_json
    assert row[3] == "test123"  # device_id
    assert row[4] == "air"  # device_type
    assert row[5] == 72.5  # temperature
    assert row[6] == 45.0  # humidity
    assert row[7] == 100  # battery
    assert row[8] == -50  # signal

    store.close()


def test_storage_batching(test_db_path):
    """Test that batching works correctly."""
    store = MessageStore(test_db_path, batch_size=5)
    store.create_table("test_messages")

    # Insert 3 messages (below batch size)
    for i in range(3):
        store.insert_message(
            "test_messages",
            f"test/topic/{i}",
            f"payload {i}".encode(),
        )

    # Should not be flushed yet
    messages = store.query("test_messages", limit=10)
    assert len(messages) == 0

    # Insert 2 more to trigger batch
    for i in range(3, 5):
        store.insert_message(
            "test_messages",
            f"test/topic/{i}",
            f"payload {i}".encode(),
        )

    # Should be flushed now
    messages = store.query("test_messages", limit=10)
    assert len(messages) == 5

    store.close()


