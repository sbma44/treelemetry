"""Tests for application module."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.mqtt_logger.app import MQTTLoggerApp


@pytest.fixture
def config_file():
    """Create a temporary config file."""
    config_content = """
[mqtt]
broker = "localhost"
port = 1883
qos = 1

[database]
path = "test.db"
batch_size = 10
flush_interval = 5

[[topics]]
pattern = "sensors/#"
table_name = "sensors"

[[topics]]
pattern = "devices/+/status"
table_name = "device_status"

[logging]
level = "INFO"
"""
    
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".toml", delete=False
    ) as f:
        f.write(config_content)
        f.flush()
        config_path = f.name
    
    yield config_path
    
    # Clean up after test
    Path(config_path).unlink(missing_ok=True)


def test_app_init(config_file):
    """Test application initialization."""
    app = MQTTLoggerApp(config_file)
    
    assert app.config is not None
    assert app.config.mqtt.broker == "localhost"
    assert len(app.config.topics) == 2
    assert not app._running


def test_topic_matches_pattern():
    """Test topic pattern matching."""
    # Exact match
    assert MQTTLoggerApp._topic_matches_pattern(
        "sensors/temp", "sensors/temp"
    )
    
    # Single-level wildcard
    assert MQTTLoggerApp._topic_matches_pattern(
        "sensors/temp", "sensors/+"
    )
    assert MQTTLoggerApp._topic_matches_pattern(
        "devices/1/status", "devices/+/status"
    )
    
    # Multi-level wildcard
    assert MQTTLoggerApp._topic_matches_pattern(
        "sensors/temp/room1", "sensors/#"
    )
    assert MQTTLoggerApp._topic_matches_pattern(
        "sensors/temp/room1/sensor1", "sensors/#"
    )
    
    # No match
    assert not MQTTLoggerApp._topic_matches_pattern(
        "devices/temp", "sensors/+"
    )
    assert not MQTTLoggerApp._topic_matches_pattern(
        "sensors/temp/room1", "sensors/+"
    )


def test_find_table_for_topic(config_file):
    """Test finding table for topic."""
    app = MQTTLoggerApp(config_file)
    
    # Test matching patterns
    assert app._find_table_for_topic("sensors/temp") == "sensors"
    assert app._find_table_for_topic("sensors/temp/room1") == "sensors"
    assert app._find_table_for_topic("devices/1/status") == "device_status"
    assert app._find_table_for_topic("devices/abc/status") == "device_status"
    
    # Test non-matching topic
    assert app._find_table_for_topic("other/topic") is None


def test_find_table_for_topic_caching(config_file):
    """Test that topic to table mapping is cached."""
    app = MQTTLoggerApp(config_file)
    
    # First call
    table1 = app._find_table_for_topic("sensors/temp")
    
    # Second call should use cache
    table2 = app._find_table_for_topic("sensors/temp")
    
    assert table1 == table2
    assert "sensors/temp" in app._topic_table_map


@patch("src.mqtt_logger.app.MessageStore")
def test_handle_message(mock_store_class, config_file):
    """Test handling messages."""
    mock_store = Mock()
    mock_store_class.return_value = mock_store
    
    app = MQTTLoggerApp(config_file)
    app.store = mock_store
    
    # Handle a message
    app._handle_message("sensors/temp", b"23.5", 1, False)
    
    # Verify message was stored
    mock_store.insert_message.assert_called_once_with(
        "sensors", "sensors/temp", b"23.5", 1, False
    )


@patch("src.mqtt_logger.app.MessageStore")
def test_handle_message_no_table(mock_store_class, config_file):
    """Test handling message with no matching table."""
    mock_store = Mock()
    mock_store_class.return_value = mock_store
    
    app = MQTTLoggerApp(config_file)
    app.store = mock_store
    
    # Handle a message with no matching topic
    app._handle_message("unknown/topic", b"data", 0, False)
    
    # Verify message was not stored
    mock_store.insert_message.assert_not_called()


@patch("src.mqtt_logger.app.MessageStore")
def test_handle_message_error(mock_store_class, config_file):
    """Test handling message with storage error."""
    mock_store = Mock()
    mock_store.insert_message.side_effect = Exception("Storage error")
    mock_store_class.return_value = mock_store
    
    app = MQTTLoggerApp(config_file)
    app.store = mock_store
    
    # Should not raise exception
    app._handle_message("sensors/temp", b"23.5", 1, False)


def test_app_init_missing_config():
    """Test app initialization with missing config."""
    with pytest.raises(FileNotFoundError):
        MQTTLoggerApp("nonexistent.toml")


def test_signal_handler(config_file):
    """Test signal handler."""
    app = MQTTLoggerApp(config_file)
    app._running = True
    
    # Simulate signal
    app._signal_handler(15, None)  # SIGTERM
    
    # Should initiate shutdown
    assert app._shutdown_event.is_set()


@patch("src.mqtt_logger.app.MessageStore")
@patch("src.mqtt_logger.app.MQTTLogger")
def test_initialize_storage(mock_mqtt_class, mock_store_class, config_file):
    """Test storage initialization."""
    mock_store = Mock()
    mock_store_class.return_value = mock_store
    
    app = MQTTLoggerApp(config_file)
    app._initialize_storage()
    
    # Verify store was created
    assert app.store is not None
    
    # Verify tables were created
    assert mock_store.create_table.call_count == 2
    mock_store.create_table.assert_any_call("sensors")
    mock_store.create_table.assert_any_call("device_status")


@patch("src.mqtt_logger.app.MessageStore")
@patch("src.mqtt_logger.app.MQTTLogger")
def test_initialize_mqtt(mock_mqtt_class, mock_store_class, config_file):
    """Test MQTT client initialization."""
    mock_mqtt = Mock()
    mock_mqtt_class.return_value = mock_mqtt
    
    app = MQTTLoggerApp(config_file)
    app._initialize_mqtt()
    
    # Verify MQTT client was created
    assert app.mqtt_client is not None
    
    # Verify subscriptions
    assert mock_mqtt.subscribe.call_count == 2

