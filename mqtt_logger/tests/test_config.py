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
    YoLinkConfig,
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


def test_yolink_config_defaults():
    """Test YoLinkConfig with defaults."""
    config = YoLinkConfig()
    assert config.enabled is False
    assert config.uaid is None
    assert config.secret_key is None
    assert config.air_sensor_device_id is None
    assert config.water_sensor_device_id is None
    assert config.table_name == "yolink_sensors"
    assert config.reconnect_delay == 5
    assert config.max_reconnect_delay == 300


def test_yolink_config_custom():
    """Test YoLinkConfig with custom values."""
    config = YoLinkConfig(
        enabled=True,
        uaid="test_uaid",
        secret_key="test_secret",
        air_sensor_device_id="air123",
        water_sensor_device_id="water456",
        table_name="custom_table",
        reconnect_delay=10,
        max_reconnect_delay=600,
    )
    assert config.enabled is True
    assert config.uaid == "test_uaid"
    assert config.secret_key == "test_secret"
    assert config.air_sensor_device_id == "air123"
    assert config.water_sensor_device_id == "water456"
    assert config.table_name == "custom_table"
    assert config.reconnect_delay == 10
    assert config.max_reconnect_delay == 600


def test_load_config_with_yolink():
    """Test loading configuration with yolink section."""
    config_content = """
[mqtt]
broker = "localhost"

[database]
path = "test.db"

[[topics]]
pattern = "test/#"
table_name = "test"

[yolink]
enabled = true
uaid = "test_uaid"
secret_key = "test_secret"
air_sensor_device_id = "air123"
water_sensor_device_id = "water456"
table_name = "yolink_data"
"""
    
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(config_content)
        config_path = f.name
    
    try:
        config = load_config(config_path)
        
        assert config.yolink.enabled is True
        assert config.yolink.uaid == "test_uaid"
        assert config.yolink.secret_key == "test_secret"
        assert config.yolink.air_sensor_device_id == "air123"
        assert config.yolink.water_sensor_device_id == "water456"
        assert config.yolink.table_name == "yolink_data"
        
    finally:
        Path(config_path).unlink()


def test_load_config_yolink_defaults():
    """Test loading configuration without yolink section uses defaults."""
    config_content = """
[mqtt]
broker = "localhost"

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
        config = load_config(config_path)
        
        # Should have default YoLink config
        assert config.yolink.enabled is False
        assert config.yolink.uaid is None
        assert config.yolink.table_name == "yolink_sensors"
        
    finally:
        Path(config_path).unlink()


def test_load_config_yolink_env_var_override():
    """Test that YoLink environment variables override TOML values."""
    import os
    
    config_content = """
[mqtt]
broker = "localhost"

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
        # Set environment variables
        os.environ["YOLINK_UAID"] = "env_uaid"
        os.environ["YOLINK_SECRET_KEY"] = "env_secret"
        os.environ["YOLINK_AIR_SENSOR_DEVICEID"] = "env_air123"
        os.environ["YOLINK_WATER_SENSOR_DEVICEID"] = "env_water456"
        os.environ["YOLINK_TABLE_NAME"] = "env_table"
        
        config = load_config(config_path)
        
        # Verify env vars enable and configure YoLink
        assert config.yolink.enabled is True  # Auto-enabled when credentials provided
        assert config.yolink.uaid == "env_uaid"
        assert config.yolink.secret_key == "env_secret"
        assert config.yolink.air_sensor_device_id == "env_air123"
        assert config.yolink.water_sensor_device_id == "env_water456"
        assert config.yolink.table_name == "env_table"
        
    finally:
        # Clean up environment variables
        os.environ.pop("YOLINK_UAID", None)
        os.environ.pop("YOLINK_SECRET_KEY", None)
        os.environ.pop("YOLINK_AIR_SENSOR_DEVICEID", None)
        os.environ.pop("YOLINK_WATER_SENSOR_DEVICEID", None)
        os.environ.pop("YOLINK_TABLE_NAME", None)
        Path(config_path).unlink()


def test_load_config_yolink_auto_enable():
    """Test that YoLink is auto-enabled when credentials are provided."""
    config_content = """
[mqtt]
broker = "localhost"

[database]
path = "test.db"

[[topics]]
pattern = "test/#"
table_name = "test"

[yolink]
uaid = "test_uaid"
secret_key = "test_secret"
"""
    
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(config_content)
        config_path = f.name
    
    try:
        config = load_config(config_path)
        
        # Should be auto-enabled when credentials are provided
        assert config.yolink.enabled is True
        
    finally:
        Path(config_path).unlink()

