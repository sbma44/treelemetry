"""Tests for MQTT client module."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from src.mqtt_logger.config import MQTTConfig
from src.mqtt_logger.mqtt_client import MQTTLogger


@pytest.fixture
def mqtt_config():
    """Create a test MQTT configuration."""
    return MQTTConfig(
        broker="test.mosquitto.org",
        port=1883,
        username="testuser",
        password="testpass",
        qos=1,
    )


@pytest.fixture
def message_callback():
    """Create a mock message callback."""
    return Mock()


def test_mqtt_logger_init(mqtt_config, message_callback):
    """Test MQTTLogger initialization."""
    client = MQTTLogger(mqtt_config, message_callback)
    
    assert client.config == mqtt_config
    assert client.message_callback == message_callback
    assert not client._connected
    assert client._should_reconnect


def test_mqtt_logger_subscribe(mqtt_config, message_callback):
    """Test subscribing to topics."""
    client = MQTTLogger(mqtt_config, message_callback)
    
    # Subscribe to a topic
    client.subscribe("test/topic/#")
    
    assert len(client._subscriptions) == 1
    assert client._subscriptions[0] == ("test/topic/#", 1)


def test_mqtt_logger_subscribe_custom_qos(mqtt_config, message_callback):
    """Test subscribing with custom QoS."""
    client = MQTTLogger(mqtt_config, message_callback)
    
    client.subscribe("test/topic", qos=2)
    
    assert client._subscriptions[0] == ("test/topic", 2)


@patch("src.mqtt_logger.mqtt_client.mqtt.Client")
def test_mqtt_logger_connect(mock_client_class, mqtt_config, message_callback):
    """Test connecting to broker."""
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    
    client = MQTTLogger(mqtt_config, message_callback)
    client.connect()
    
    mock_client.connect.assert_called_once_with(
        mqtt_config.broker,
        mqtt_config.port,
        mqtt_config.keepalive,
    )


@patch("src.mqtt_logger.mqtt_client.mqtt.Client")
def test_mqtt_logger_disconnect(mock_client_class, mqtt_config, message_callback):
    """Test disconnecting from broker."""
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    
    client = MQTTLogger(mqtt_config, message_callback)
    client.disconnect()
    
    assert not client._should_reconnect
    mock_client.disconnect.assert_called_once()


@patch("src.mqtt_logger.mqtt_client.mqtt.Client")
def test_on_connect_callback(mock_client_class, mqtt_config, message_callback):
    """Test on_connect callback."""
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    
    client = MQTTLogger(mqtt_config, message_callback)
    client.subscribe("test/topic")
    
    # Simulate successful connection
    client._on_connect(mock_client, None, None, 0)
    
    assert client._connected
    mock_client.subscribe.assert_called()


@patch("src.mqtt_logger.mqtt_client.mqtt.Client")
def test_on_disconnect_callback(mock_client_class, mqtt_config, message_callback):
    """Test on_disconnect callback."""
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    
    client = MQTTLogger(mqtt_config, message_callback)
    client._connected = True
    
    # Simulate disconnection
    client._on_disconnect(mock_client, None, None, 1)
    
    assert not client._connected


@patch("src.mqtt_logger.mqtt_client.mqtt.Client")
def test_on_message_callback(mock_client_class, mqtt_config, message_callback):
    """Test on_message callback."""
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    
    client = MQTTLogger(mqtt_config, message_callback)
    
    # Create a mock message
    mock_message = Mock()
    mock_message.topic = "test/topic"
    mock_message.payload = b"test payload"
    mock_message.qos = 1
    mock_message.retain = False
    
    # Simulate message receipt
    client._on_message(mock_client, None, mock_message)
    
    # Verify callback was called with correct arguments
    message_callback.assert_called_once_with(
        "test/topic",
        b"test payload",
        1,
        False,
    )


@patch("src.mqtt_logger.mqtt_client.mqtt.Client")
def test_on_message_callback_error(mock_client_class, mqtt_config, message_callback):
    """Test on_message callback with error."""
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    
    # Make callback raise an exception
    message_callback.side_effect = Exception("Test error")
    
    client = MQTTLogger(mqtt_config, message_callback)
    
    mock_message = Mock()
    mock_message.topic = "test/topic"
    mock_message.payload = b"test"
    mock_message.qos = 0
    mock_message.retain = False
    
    # Should not raise exception
    client._on_message(mock_client, None, mock_message)


@patch("src.mqtt_logger.mqtt_client.mqtt.Client")
def test_authentication(mock_client_class, message_callback):
    """Test MQTT authentication."""
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    
    config = MQTTConfig(
        broker="localhost",
        username="user",
        password="pass",
    )
    
    client = MQTTLogger(config, message_callback)
    
    mock_client.username_pw_set.assert_called_once_with("user", "pass")


@patch("src.mqtt_logger.mqtt_client.mqtt.Client")
def test_no_authentication(mock_client_class, message_callback):
    """Test MQTT without authentication."""
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    
    config = MQTTConfig(broker="localhost")
    
    client = MQTTLogger(config, message_callback)
    
    mock_client.username_pw_set.assert_not_called()

