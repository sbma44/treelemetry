"""Tests for configuration module."""

import tempfile
from pathlib import Path

import pytest

from src.mqtt_logger.config import (
    AlertingConfig,
    Config,
    DatabaseConfig,
    LoggingConfig,
    MQTTConfig,
    TopicConfig,
    load_config,
)


def test_mqtt_config_defaults():
    """Test MQTTConfig with default values."""
    config = MQTTConfig(broker="localhost")
    assert config.broker == "localhost"
    assert config.port == 1883
    assert config.username is None
    assert config.password is None
    assert config.client_id is None
    assert config.keepalive == 60
    assert config.qos == 1


def test_mqtt_config_custom():
    """Test MQTTConfig with custom values."""
    config = MQTTConfig(
        broker="mqtt.example.com",
        port=8883,
        username="user",
        password="pass",
        client_id="test_client",
        keepalive=30,
        qos=2,
    )
    assert config.broker == "mqtt.example.com"
    assert config.port == 8883
    assert config.username == "user"
    assert config.password == "pass"
    assert config.client_id == "test_client"
    assert config.keepalive == 30
    assert config.qos == 2


def test_topic_config():
    """Test TopicConfig."""
    config = TopicConfig(
        pattern="sensors/#",
        table_name="sensors",
        description="All sensors",
    )
    assert config.pattern == "sensors/#"
    assert config.table_name == "sensors"
    assert config.description == "All sensors"


def test_database_config_defaults():
    """Test DatabaseConfig with defaults."""
    config = DatabaseConfig(path="test.db")
    assert config.path == "test.db"
    assert config.batch_size == 1000
    assert config.flush_interval == 60


def test_logging_config_defaults():
    """Test LoggingConfig with defaults."""
    config = LoggingConfig()
    assert config.level == "INFO"
    assert "%(asctime)s" in config.format
    assert config.file is None


def test_alerting_config_defaults():
    """Test AlertingConfig with defaults."""
    config = AlertingConfig()
    assert config.email_to is None
    assert config.db_size_threshold_mb is None
    assert config.free_space_threshold_mb is None
    assert config.alert_cooldown_hours == 24


def test_alerting_config_custom():
    """Test AlertingConfig with custom values."""
    config = AlertingConfig(
        email_to="admin@example.com",
        db_size_threshold_mb=1000,
        free_space_threshold_mb=500,
        alert_cooldown_hours=12,
    )
    assert config.email_to == "admin@example.com"
    assert config.db_size_threshold_mb == 1000
    assert config.free_space_threshold_mb == 500
    assert config.alert_cooldown_hours == 12


def test_load_config_valid():
    """Test loading a valid configuration file."""
    config_content = """
[mqtt]
broker = "mqtt.example.com"
port = 1883
username = "testuser"
password = "testpass"
qos = 1

[database]
path = "data/test.db"
batch_size = 50
flush_interval = 5

[[topics]]
pattern = "sensors/#"
table_name = "sensors"
description = "Sensor data"

[[topics]]
pattern = "devices/+/status"
table_name = "device_status"

[logging]
level = "DEBUG"
"""
    
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(config_content)
        config_path = f.name
    
    try:
        config = load_config(config_path)
        
        # Check MQTT config
        assert config.mqtt.broker == "mqtt.example.com"
        assert config.mqtt.port == 1883
        assert config.mqtt.username == "testuser"
        assert config.mqtt.password == "testpass"
        assert config.mqtt.qos == 1
        
        # Check database config
        assert config.database.path == "data/test.db"
        assert config.database.batch_size == 50
        assert config.database.flush_interval == 5
        
        # Check topics
        assert len(config.topics) == 2
        assert config.topics[0].pattern == "sensors/#"
        assert config.topics[0].table_name == "sensors"
        assert config.topics[0].description == "Sensor data"
        assert config.topics[1].pattern == "devices/+/status"
        assert config.topics[1].table_name == "device_status"
        
        # Check logging
        assert config.logging.level == "DEBUG"
        
        # Check alerting (should have defaults since not in config)
        assert config.alerting.email_to is None
        
    finally:
        Path(config_path).unlink()


def test_load_config_with_alerting():
    """Test loading configuration with alerting section."""
    config_content = """
[mqtt]
broker = "localhost"

[database]
path = "test.db"

[[topics]]
pattern = "test/#"
table_name = "test"

[alerting]
email_to = "admin@example.com"
db_size_threshold_mb = 1000
free_space_threshold_mb = 500
alert_cooldown_hours = 12
"""
    
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(config_content)
        config_path = f.name
    
    try:
        config = load_config(config_path)
        
        assert config.alerting.email_to == "admin@example.com"
        assert config.alerting.db_size_threshold_mb == 1000
        assert config.alerting.free_space_threshold_mb == 500
        assert config.alerting.alert_cooldown_hours == 12
        
    finally:
        Path(config_path).unlink()


def test_load_config_missing_file():
    """Test loading a non-existent configuration file."""
    with pytest.raises(FileNotFoundError):
        load_config("nonexistent.toml")


def test_load_config_missing_mqtt_section():
    """Test loading config without mqtt section."""
    config_content = """
[database]
path = "test.db"

[[topics]]
pattern = "test/#"
table_name = "test"
"""
    
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(config_content)
        config_path = f.name
    
    try:
        with pytest.raises(ValueError, match="Missing required section: mqtt"):
            load_config(config_path)
    finally:
        Path(config_path).unlink()


def test_load_config_missing_broker():
    """Test loading config without mqtt.broker."""
    config_content = """
[mqtt]
port = 1883

[database]
path = "test.db"

[[topics]]
pattern = "test/#"
table_name = "test"
"""
    
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(config_content)
        config_path = f.name
    
    try:
        with pytest.raises(ValueError, match="mqtt.broker is required"):
            load_config(config_path)
    finally:
        Path(config_path).unlink()


def test_load_config_missing_database_section():
    """Test loading config without database section."""
    config_content = """
[mqtt]
broker = "localhost"

[[topics]]
pattern = "test/#"
table_name = "test"
"""
    
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(config_content)
        config_path = f.name
    
    try:
        with pytest.raises(ValueError, match="Missing required section: database"):
            load_config(config_path)
    finally:
        Path(config_path).unlink()


def test_load_config_no_topics():
    """Test loading config without topics."""
    config_content = """
[mqtt]
broker = "localhost"

[database]
path = "test.db"
"""
    
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(config_content)
        config_path = f.name
    
    try:
        with pytest.raises(ValueError, match="At least one topic must be configured"):
            load_config(config_path)
    finally:
        Path(config_path).unlink()


def test_load_config_topic_missing_pattern():
    """Test loading config with topic missing pattern."""
    config_content = """
[mqtt]
broker = "localhost"

[database]
path = "test.db"

[[topics]]
table_name = "test"
"""
    
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(config_content)
        config_path = f.name
    
    try:
        with pytest.raises(ValueError, match="topic.pattern is required"):
            load_config(config_path)
    finally:
        Path(config_path).unlink()


def test_load_config_topic_missing_table_name():
    """Test loading config with topic missing table_name."""
    config_content = """
[mqtt]
broker = "localhost"

[database]
path = "test.db"

[[topics]]
pattern = "test/#"
"""
    
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(config_content)
        config_path = f.name
    
    try:
        with pytest.raises(ValueError, match="topic.table_name is required"):
            load_config(config_path)
    finally:
        Path(config_path).unlink()


def test_load_config_env_var_override():
    """Test that environment variables override TOML values."""
    import os
    
    config_content = """
[mqtt]
broker = "localhost"
port = 1883

[database]
path = "test.db"
batch_size = 100
flush_interval = 10

[[topics]]
pattern = "test/#"
table_name = "test"
"""
    
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(config_content)
        config_path = f.name
    
    try:
        # Set environment variables
        os.environ["DB_BATCH_SIZE"] = "5000"
        os.environ["DB_FLUSH_INTERVAL"] = "300"
        os.environ["MQTT_PORT"] = "8883"
        
        config = load_config(config_path)
        
        # Verify env vars override TOML values
        assert config.database.batch_size == 5000  # Override from env
        assert config.database.flush_interval == 300  # Override from env
        assert config.mqtt.port == 8883  # Override from env
        assert config.database.path == "test.db"  # Not overridden
        
    finally:
        # Clean up environment variables
        os.environ.pop("DB_BATCH_SIZE", None)
        os.environ.pop("DB_FLUSH_INTERVAL", None)
        os.environ.pop("MQTT_PORT", None)
        Path(config_path).unlink()

