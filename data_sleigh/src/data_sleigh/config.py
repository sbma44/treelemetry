"""Configuration management for Data Sleigh."""

import os
import tomllib
from dataclasses import dataclass
from datetime import date
from pathlib import Path


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
class YoLinkConfig:
    """YoLink integration configuration.

    Attributes:
        enabled: Whether YoLink integration is enabled
        uaid: YoLink User Access ID (UAID)
        secret_key: YoLink Secret Key
        air_sensor_device_id: Device ID for the air temperature/humidity sensor
        water_sensor_device_id: Device ID for the water temperature sensor
        table_name: DuckDB table name for storing YoLink sensor data
        reconnect_delay: Seconds to wait before reconnecting after disconnection
        max_reconnect_delay: Maximum reconnect delay (exponential backoff cap)
    """

    enabled: bool = False
    uaid: str | None = None
    secret_key: str | None = None
    air_sensor_device_id: str | None = None
    water_sensor_device_id: str | None = None
    table_name: str = "yolink_sensors"
    reconnect_delay: int = 5
    max_reconnect_delay: int = 300


@dataclass
class MQTTEchoConfig:
    """Configuration for echoing YoLink MQTT messages to a local broker.

    Attributes:
        enabled: Whether MQTT echo is enabled
        broker: MQTT broker hostname or IP address
        port: MQTT broker port (default: 1883)
        username: Optional username for authentication (None = no auth)
        password: Optional password for authentication (None = no auth)
        client_id: Optional client ID (auto-generated if not provided)
        topic_prefix: Prefix for echoed messages (default: "yolink")
        qos: Quality of Service level (0, 1, or 2)
    """

    enabled: bool = False
    broker: str | None = None
    port: int = 1883
    username: str | None = None
    password: str | None = None
    client_id: str | None = None
    topic_prefix: str = "yolink"
    qos: int = 1


@dataclass
class SeasonConfig:
    """Season configuration for upload behavior.

    Attributes:
        start: Start date of the season (ISO format YYYY-MM-DD)
        end: End date of the season (ISO format YYYY-MM-DD)

    During the season, JSON is uploaded to S3 for the live website.
    Outside the season, no JSON uploads occur but data collection continues.
    """

    start: date
    end: date


@dataclass
class S3Config:
    """S3 configuration for uploads and backups.

    Attributes:
        bucket: S3 bucket name
        json_key: S3 key for website JSON data
        backup_prefix: S3 prefix for database backups
        aws_access_key_id: AWS access key ID
        aws_secret_access_key: AWS secret access key
    """

    bucket: str
    json_key: str = "water-level.json"
    backup_prefix: str = "backups/"
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None


@dataclass
class UploadConfig:
    """Upload behavior configuration.

    Attributes:
        interval_seconds: Upload interval in seconds (during season)
        minutes_of_data: Minutes of historical data to include in JSON
        replay_delay_seconds: Delay for visualization replay
    """

    interval_seconds: int = 30
    minutes_of_data: int = 10
    replay_delay_seconds: int = 300


@dataclass
class BackupConfig:
    """Monthly backup configuration.

    Attributes:
        day_of_month: Day of month to run backup (1-31)
        hour: Hour of day to run backup (0-23)
    """

    day_of_month: int = 1
    hour: int = 3


@dataclass
class Config:
    """Main application configuration.

    Attributes:
        mqtt: MQTT broker configuration
        database: Database configuration
        topics: List of topic configurations
        logging: Logging configuration
        alerting: Alerting configuration
        yolink: YoLink integration configuration
        mqtt_echo: Configuration for echoing YoLink messages to local MQTT
        season: Season configuration for upload behavior
        s3: S3 configuration for uploads and backups
        upload: Upload behavior configuration
        backup: Monthly backup configuration
    """

    mqtt: MQTTConfig
    database: DatabaseConfig
    topics: list[TopicConfig]
    logging: LoggingConfig
    alerting: AlertingConfig
    yolink: YoLinkConfig
    mqtt_echo: MQTTEchoConfig
    season: SeasonConfig
    s3: S3Config
    upload: UploadConfig
    backup: BackupConfig


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
        >>> config = load_config("config/data_sleigh.toml")
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
    if "season" not in data:
        raise ValueError("Missing required section: season")
    if "s3" not in data:
        raise ValueError("Missing required section: s3")

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

    # Parse YoLink config (optional)
    yolink_data = data.get("yolink", {})

    # Override with environment variables if set
    if os.getenv("YOLINK_UAID"):
        yolink_data["uaid"] = os.getenv("YOLINK_UAID")
        yolink_data["enabled"] = True
    if os.getenv("YOLINK_SECRET_KEY"):
        yolink_data["secret_key"] = os.getenv("YOLINK_SECRET_KEY")
    if os.getenv("YOLINK_AIR_SENSOR_DEVICEID"):
        yolink_data["air_sensor_device_id"] = os.getenv("YOLINK_AIR_SENSOR_DEVICEID")
    if os.getenv("YOLINK_WATER_SENSOR_DEVICEID"):
        yolink_data["water_sensor_device_id"] = os.getenv("YOLINK_WATER_SENSOR_DEVICEID")
    if os.getenv("YOLINK_TABLE_NAME"):
        yolink_data["table_name"] = os.getenv("YOLINK_TABLE_NAME")
    if os.getenv("YOLINK_RECONNECT_DELAY"):
        yolink_data["reconnect_delay"] = int(os.getenv("YOLINK_RECONNECT_DELAY"))
    if os.getenv("YOLINK_MAX_RECONNECT_DELAY"):
        yolink_data["max_reconnect_delay"] = int(os.getenv("YOLINK_MAX_RECONNECT_DELAY"))

    # Auto-enable if credentials are provided
    if yolink_data.get("uaid") and yolink_data.get("secret_key"):
        yolink_data["enabled"] = True

    yolink_config = YoLinkConfig(**yolink_data)

    # Parse MQTT echo config (optional)
    mqtt_echo_data = data.get("mqtt_echo", {})

    # Override with environment variables if set
    if os.getenv("MQTT_ECHO_ENABLED"):
        mqtt_echo_data["enabled"] = os.getenv("MQTT_ECHO_ENABLED").lower() in ("true", "1", "yes")
    if os.getenv("MQTT_ECHO_BROKER"):
        mqtt_echo_data["broker"] = os.getenv("MQTT_ECHO_BROKER")
        # Auto-enable if broker is specified
        mqtt_echo_data["enabled"] = True
    if os.getenv("MQTT_ECHO_PORT"):
        mqtt_echo_data["port"] = int(os.getenv("MQTT_ECHO_PORT"))
    if os.getenv("MQTT_ECHO_USERNAME"):
        mqtt_echo_data["username"] = os.getenv("MQTT_ECHO_USERNAME")
    if os.getenv("MQTT_ECHO_PASSWORD"):
        mqtt_echo_data["password"] = os.getenv("MQTT_ECHO_PASSWORD")
    if os.getenv("MQTT_ECHO_CLIENT_ID"):
        mqtt_echo_data["client_id"] = os.getenv("MQTT_ECHO_CLIENT_ID")
    if os.getenv("MQTT_ECHO_TOPIC_PREFIX"):
        mqtt_echo_data["topic_prefix"] = os.getenv("MQTT_ECHO_TOPIC_PREFIX")
    if os.getenv("MQTT_ECHO_QOS"):
        mqtt_echo_data["qos"] = int(os.getenv("MQTT_ECHO_QOS"))

    mqtt_echo_config = MQTTEchoConfig(**mqtt_echo_data)

    # Parse season config
    season_data = data["season"]
    if "start" not in season_data:
        raise ValueError("season.start is required")
    if "end" not in season_data:
        raise ValueError("season.end is required")

    # Override with environment variables if set
    if os.getenv("SEASON_START"):
        season_data["start"] = os.getenv("SEASON_START")
    if os.getenv("SEASON_END"):
        season_data["end"] = os.getenv("SEASON_END")

    # Parse dates (handle both date objects and strings)
    if isinstance(season_data["start"], str):
        season_data["start"] = date.fromisoformat(season_data["start"])
    if isinstance(season_data["end"], str):
        season_data["end"] = date.fromisoformat(season_data["end"])

    season_config = SeasonConfig(**season_data)

    # Parse S3 config
    s3_data = data["s3"]
    if "bucket" not in s3_data:
        raise ValueError("s3.bucket is required")

    # Override with environment variables if set
    if os.getenv("S3_BUCKET"):
        s3_data["bucket"] = os.getenv("S3_BUCKET")
    if os.getenv("S3_JSON_KEY"):
        s3_data["json_key"] = os.getenv("S3_JSON_KEY")
    if os.getenv("S3_BACKUP_PREFIX"):
        s3_data["backup_prefix"] = os.getenv("S3_BACKUP_PREFIX")
    if os.getenv("AWS_ACCESS_KEY_ID"):
        s3_data["aws_access_key_id"] = os.getenv("AWS_ACCESS_KEY_ID")
    if os.getenv("AWS_SECRET_ACCESS_KEY"):
        s3_data["aws_secret_access_key"] = os.getenv("AWS_SECRET_ACCESS_KEY")

    s3_config = S3Config(**s3_data)

    # Parse upload config (optional)
    upload_data = data.get("upload", {})

    # Override with environment variables if set
    if os.getenv("UPLOAD_INTERVAL_SECONDS"):
        upload_data["interval_seconds"] = int(os.getenv("UPLOAD_INTERVAL_SECONDS"))
    if os.getenv("MINUTES_OF_DATA"):
        upload_data["minutes_of_data"] = int(os.getenv("MINUTES_OF_DATA"))
    if os.getenv("REPLAY_DELAY_SECONDS"):
        upload_data["replay_delay_seconds"] = int(os.getenv("REPLAY_DELAY_SECONDS"))

    upload_config = UploadConfig(**upload_data)

    # Parse backup config (optional)
    backup_data = data.get("backup", {})

    # Override with environment variables if set
    if os.getenv("BACKUP_DAY_OF_MONTH"):
        backup_data["day_of_month"] = int(os.getenv("BACKUP_DAY_OF_MONTH"))
    if os.getenv("BACKUP_HOUR"):
        backup_data["hour"] = int(os.getenv("BACKUP_HOUR"))

    backup_config = BackupConfig(**backup_data)

    return Config(
        mqtt=mqtt_config,
        database=database_config,
        topics=topics,
        logging=logging_config,
        alerting=alerting_config,
        yolink=yolink_config,
        mqtt_echo=mqtt_echo_config,
        season=season_config,
        s3=s3_config,
        upload=upload_config,
        backup=backup_config,
    )




