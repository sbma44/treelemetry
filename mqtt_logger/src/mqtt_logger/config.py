"""Configuration management for MQTT Logger."""

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


@dataclass
class MQTTConfig:
    """MQTT broker configuration.

    Attributes:
        broker: MQTT broker hostname or IP address
        port: MQTT broker port (default: 1883)
        username: Optional username for authentication
        password: Optional password for authentication
        client_id: Optional client ID (auto-generated if not provided)
        keepalive: Keep-alive interval in seconds (default: 60)
        qos: Quality of Service level (0, 1, or 2)
    """

    broker: str
    port: int = 1883
    username: str | None = None
    password: str | None = None
    client_id: str | None = None
    keepalive: int = 60
    qos: int = 1


@dataclass
class TopicConfig:
    """MQTT topic configuration.

    Attributes:
        pattern: MQTT topic pattern (can include wildcards)
        table_name: DuckDB table name for storing messages
        description: Optional description of the topic
    """

    pattern: str
    table_name: str
    description: str | None = None


@dataclass
class DatabaseConfig:
    """Database configuration.

    Attributes:
        path: Path to DuckDB database file
        batch_size: Number of messages to batch before writing (default: 1000)
        flush_interval: Seconds between forced flushes (default: 60)
    """

    path: str
    batch_size: int = 1000
    flush_interval: int = 60


@dataclass
class LoggingConfig:
    """Logging configuration.

    Attributes:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format: Log message format string
        file: Optional log file path
    """

    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file: str | None = None


@dataclass
class AlertingConfig:
    """Alerting configuration for disk space monitoring.

    Attributes:
        email_to: Email address to send alerts to (None = disabled)
        db_size_threshold_mb: Alert when database exceeds this size in MB (None = disabled)
        free_space_threshold_mb: Alert when free space drops below this in MB (None = disabled)
        alert_cooldown_hours: Hours to wait between repeat alerts (default: 24)
    """

    email_to: str | None = None
    db_size_threshold_mb: int | None = None
    free_space_threshold_mb: int | None = None
    alert_cooldown_hours: int = 24


@dataclass
class Config:
    """Main application configuration.

    Attributes:
        mqtt: MQTT broker configuration
        database: Database configuration
        topics: List of topic configurations
        logging: Logging configuration
        alerting: Alerting configuration (optional)
    """

    mqtt: MQTTConfig
    database: DatabaseConfig
    topics: list[TopicConfig]
    logging: LoggingConfig
    alerting: AlertingConfig


def load_config(config_path: Path | str) -> Config:
    """Load configuration from a TOML file.

    Args:
        config_path: Path to the configuration file

    Returns:
        Parsed configuration object

    Raises:
        FileNotFoundError: If configuration file doesn't exist
        ValueError: If configuration is invalid

    Example:
        >>> config = load_config("config/mqtt_logger.toml")
        >>> print(config.mqtt.broker)
        'localhost'
    """
    config_path = Path(config_path)

    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_path, "rb") as f:
        data = tomllib.load(f)

    # Validate required sections
    if "mqtt" not in data:
        raise ValueError("Missing required section: mqtt")
    if "database" not in data:
        raise ValueError("Missing required section: database")
    if "topics" not in data or not data["topics"]:
        raise ValueError("At least one topic must be configured")

    # Parse MQTT config
    mqtt_data = data["mqtt"]
    if "broker" not in mqtt_data:
        raise ValueError("mqtt.broker is required")

    # Override with environment variables if set
    if os.getenv("MQTT_BROKER"):
        mqtt_data["broker"] = os.getenv("MQTT_BROKER")
    if os.getenv("MQTT_PORT"):
        mqtt_data["port"] = int(os.getenv("MQTT_PORT"))
    if os.getenv("MQTT_USERNAME"):
        mqtt_data["username"] = os.getenv("MQTT_USERNAME")
    if os.getenv("MQTT_PASSWORD"):
        mqtt_data["password"] = os.getenv("MQTT_PASSWORD")
    if os.getenv("MQTT_CLIENT_ID"):
        mqtt_data["client_id"] = os.getenv("MQTT_CLIENT_ID")
    if os.getenv("MQTT_KEEPALIVE"):
        mqtt_data["keepalive"] = int(os.getenv("MQTT_KEEPALIVE"))
    if os.getenv("MQTT_QOS"):
        mqtt_data["qos"] = int(os.getenv("MQTT_QOS"))

    mqtt_config = MQTTConfig(**mqtt_data)

    # Parse database config
    db_data = data["database"]
    if "path" not in db_data:
        raise ValueError("database.path is required")

    # Override with environment variables if set
    if os.getenv("DB_PATH"):
        db_data["path"] = os.getenv("DB_PATH")
    if os.getenv("DB_BATCH_SIZE"):
        db_data["batch_size"] = int(os.getenv("DB_BATCH_SIZE"))
    if os.getenv("DB_FLUSH_INTERVAL"):
        db_data["flush_interval"] = int(os.getenv("DB_FLUSH_INTERVAL"))

    database_config = DatabaseConfig(**db_data)

    # Parse topics
    topics = []
    for topic_data in data["topics"]:
        if "pattern" not in topic_data:
            raise ValueError("topic.pattern is required")
        if "table_name" not in topic_data:
            raise ValueError("topic.table_name is required")
        topics.append(TopicConfig(**topic_data))

    # Parse logging config (optional)
    logging_data = data.get("logging", {})

    # Override with environment variables if set
    if os.getenv("LOG_LEVEL"):
        logging_data["level"] = os.getenv("LOG_LEVEL")
    if os.getenv("LOG_FILE"):
        logging_data["file"] = os.getenv("LOG_FILE")

    logging_config = LoggingConfig(**logging_data)

    # Parse alerting config (optional)
    alerting_data = data.get("alerting", {})

    # Override with environment variables if set
    if os.getenv("ALERT_EMAIL_TO"):
        alerting_data["email_to"] = os.getenv("ALERT_EMAIL_TO")
    if os.getenv("ALERT_DB_SIZE_MB"):
        alerting_data["db_size_threshold_mb"] = int(os.getenv("ALERT_DB_SIZE_MB"))
    if os.getenv("ALERT_FREE_SPACE_MB"):
        alerting_data["free_space_threshold_mb"] = int(os.getenv("ALERT_FREE_SPACE_MB"))
    if os.getenv("ALERT_COOLDOWN_HOURS"):
        alerting_data["alert_cooldown_hours"] = int(os.getenv("ALERT_COOLDOWN_HOURS"))

    alerting_config = AlertingConfig(**alerting_data)

    return Config(
        mqtt=mqtt_config,
        database=database_config,
        topics=topics,
        logging=logging_config,
        alerting=alerting_config,
    )

