"""Main application logic for Data Sleigh."""

import logging
import signal
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from .aggregator import (
    query_aggregated_data,
    query_water_levels,
    query_yolink_aggregated_data,
)
from .alerting import AlertManager
from .analyzer import analyze_water_level_segments
from .backup import BackupManager
from .config import load_config
from .mqtt_client import MQTTLogger
from .storage import MessageStore
from .uploader import create_json_output, upload_to_s3
from .yolink_client import YoLinkClient

logger = logging.getLogger(__name__)


class DataSleighApp:
    """Main application for Data Sleigh.

    Manages MQTT data collection, YoLink integration, DuckDB storage,
    S3 uploads with season awareness, and monthly backups during off-season.

    Example:
        >>> app = DataSleighApp("config/data_sleigh.toml")
        >>> app.run()
    """

    def __init__(self, config_path: str | Path):
        """Initialize the application.

        Args:
            config_path: Path to configuration file
        """
        self.config = load_config(config_path)
        self._setup_logging()

        self.store: MessageStore | None = None
        self.mqtt_client: MQTTLogger | None = None
        self.alert_manager: AlertManager | None = None
        self.yolink_client: YoLinkClient | None = None
        self.backup_manager: BackupManager | None = None

        self._running = False
        self._shutdown_event = threading.Event()

        # Map topics to table names
        self._topic_table_map: dict[str, str] = {}

        # Cache for analysis results
        self._cached_analysis = None

        logger.info("Data Sleigh application initialized")

    def _setup_logging(self) -> None:
        """Configure logging based on config."""
        log_config = self.config.logging

        # Configure root logger
        logging.basicConfig(
            level=getattr(logging, log_config.level.upper()),
            format=log_config.format,
        )

        # Add file handler if specified
        if log_config.file:
            file_handler = logging.FileHandler(log_config.file)
            file_handler.setFormatter(logging.Formatter(log_config.format))
            logging.getLogger().addHandler(file_handler)
            logger.info(f"Logging to file: {log_config.file}")

    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        logger.info("Signal handlers registered")

    def _signal_handler(self, signum: int, frame: any) -> None:
        """Handle shutdown signals.

        Args:
            signum: Signal number
            frame: Current stack frame
        """
        signal_name = signal.Signals(signum).name
        logger.info(f"Received {signal_name}, initiating graceful shutdown...")
        self.shutdown()

    def is_in_season(self) -> bool:
        """Check if current date is within the configured season.

        Returns:
            True if currently in season
        """
        now = datetime.now(timezone.utc).date()
        return self.config.season.start <= now <= self.config.season.end

    def _handle_message(
        self,
        topic: str,
        payload: bytes,
        qos: int,
        retain: bool,
    ) -> None:
        """Handle incoming MQTT messages.

        Args:
            topic: MQTT topic
            payload: Message payload
            qos: Quality of Service level
            retain: Whether message was retained
        """
        # Find matching table for this topic
        table_name = self._find_table_for_topic(topic)

        if table_name and self.store:
            try:
                self.store.insert_message(table_name, topic, payload, qos, retain)
            except Exception as e:
                logger.error(f"Failed to store message from {topic}: {e}")
        else:
            logger.warning(f"No table mapping found for topic: {topic}")

    def _find_table_for_topic(self, topic: str) -> str | None:
        """Find the appropriate table for a given topic.

        Args:
            topic: MQTT topic

        Returns:
            Table name or None if no match found
        """
        # Check cache first
        if topic in self._topic_table_map:
            return self._topic_table_map[topic]

        # Find matching pattern
        for topic_config in self.config.topics:
            if self._topic_matches_pattern(topic, topic_config.pattern):
                table_name = topic_config.table_name
                self._topic_table_map[topic] = table_name
                return table_name

        return None

    @staticmethod
    def _topic_matches_pattern(topic: str, pattern: str) -> bool:
        """Check if a topic matches an MQTT pattern.

        Args:
            topic: Actual MQTT topic
            pattern: Pattern with wildcards (+ for single level, # for multi-level)

        Returns:
            True if topic matches pattern
        """
        topic_parts = topic.split("/")
        pattern_parts = pattern.split("/")

        # Handle # wildcard (must be last)
        if "#" in pattern_parts:
            if pattern_parts[-1] != "#":
                return False
            pattern_parts = pattern_parts[:-1]
            topic_parts = topic_parts[: len(pattern_parts)]

        # Check length match
        if len(topic_parts) != len(pattern_parts):
            return False

        # Check each level
        for topic_part, pattern_part in zip(topic_parts, pattern_parts, strict=True):
            if pattern_part != "+" and pattern_part != topic_part:
                return False

        return True

    def _handle_yolink_sensor(
        self,
        device_type: str,
        device_id: str,
        temperature: float | None,
        humidity: float | None,
        battery: int | None,
        signal: int | None,
        raw_data: dict,
    ) -> None:
        """Handle incoming YoLink sensor data.

        Args:
            device_type: "air" or "water"
            device_id: The YoLink device ID
            temperature: Temperature reading (Fahrenheit)
            humidity: Humidity percentage (None for water sensor)
            battery: Battery level (0-100)
            signal: Signal strength (dBm)
            raw_data: Complete raw message payload
        """
        if not self.store:
            return

        table_name = self.config.yolink.table_name

        try:
            self.store.insert_yolink_message(
                device_type,
                device_id,
                temperature,
                humidity,
                battery,
                signal,
                raw_data,
                table_name,
            )
            logger.info(
                f"YoLink {device_type} sensor: temp={temperature}°F"
                + (f", humidity={humidity}%" if humidity is not None else "")
            )
        except Exception as e:
            logger.error(f"Failed to store YoLink sensor data: {e}")

    def _initialize_storage(self) -> None:
        """Initialize the database storage."""
        self.store = MessageStore(
            self.config.database.path,
            self.config.database.batch_size,
            self.config.database.flush_interval,
        )

        # Create tables for all configured topics
        for topic_config in self.config.topics:
            self.store.create_table(topic_config.table_name)
            logger.info(
                f"Table '{topic_config.table_name}' ready for "
                f"pattern '{topic_config.pattern}'"
            )

        # Create YoLink table if enabled
        if self.config.yolink.enabled:
            self.store.create_yolink_table(self.config.yolink.table_name)

    def _initialize_mqtt(self) -> None:
        """Initialize the MQTT client."""
        self.mqtt_client = MQTTLogger(
            self.config.mqtt,
            self._handle_message,
        )

        # Subscribe to all configured topics
        for topic_config in self.config.topics:
            self.mqtt_client.subscribe(
                topic_config.pattern,
                self.config.mqtt.qos,
            )

    def _initialize_alerting(self) -> None:
        """Initialize the alert manager."""
        self.alert_manager = AlertManager(
            email_to=self.config.alerting.email_to,
            db_size_threshold_mb=self.config.alerting.db_size_threshold_mb,
            free_space_threshold_mb=self.config.alerting.free_space_threshold_mb,
            alert_cooldown_hours=self.config.alerting.alert_cooldown_hours,
        )

    def _initialize_yolink(self) -> None:
        """Initialize the YoLink client if configured."""
        if not self.config.yolink.enabled:
            logger.info("YoLink integration is disabled")
            return

        if not self.config.yolink.uaid or not self.config.yolink.secret_key:
            logger.info("YoLink credentials not configured, skipping")
            return

        self.yolink_client = YoLinkClient(
            self.config.yolink,
            self._handle_yolink_sensor,
        )

    def _initialize_backup(self) -> None:
        """Initialize the backup manager."""
        self.backup_manager = BackupManager(
            self.config.backup,
            self.config.s3,
        )

    def _send_startup_notification(self) -> None:
        """Send startup success email notification."""
        if not self.config.alerting.email_to:
            return

        import socket

        hostname = socket.gethostname()
        start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z")
        in_season = self.is_in_season()

        # Format topics list
        topics_list = "\n".join([
            f"  • {t.pattern} → {t.table_name}"
            + (f" ({t.description})" if t.description else "")
            for t in self.config.topics
        ])

        subject = "Data Sleigh Started Successfully"
        body = f"""Data Sleigh has started successfully!

Container: {hostname}
Start Time: {start_time}

Season Configuration:
  Start: {self.config.season.start}
  End: {self.config.season.end}
  Currently In Season: {'YES' if in_season else 'NO'}

Season Behavior:
  {'  - Uploading JSON to S3 every ' + str(self.config.upload.interval_seconds) + 's' if in_season else '  - NO JSON uploads (off-season)'}
  {'  - Collecting data for live website' if in_season else '  - Collecting data, monthly backups enabled'}

MQTT Configuration:
  Broker: {self.config.mqtt.broker}:{self.config.mqtt.port}
  Client ID: {self.config.mqtt.client_id or '(auto-generated)'}
  QoS: {self.config.mqtt.qos}
  Username: {self.config.mqtt.username or '(none)'}

Database Configuration:
  Path: {self.config.database.path}
  Batch Size: {self.config.database.batch_size} messages
  Flush Interval: {self.config.database.flush_interval} seconds

Topics:
{topics_list}

Logging:
  Level: {self.config.logging.level}
  File: {self.config.logging.file or '(stdout/journal only)'}

Email Alerts:
  Email: {self.config.alerting.email_to}
  DB Size Threshold: {self.config.alerting.db_size_threshold_mb or '(disabled)'} MB
  Free Space Threshold: {self.config.alerting.free_space_threshold_mb or '(disabled)'} MB
  Cooldown: {self.config.alerting.alert_cooldown_hours} hours

YoLink Integration:
  Enabled: {self.config.yolink.enabled}
  Air Sensor: {self.config.yolink.air_sensor_device_id or '(not configured)'}
  Water Sensor: {self.config.yolink.water_sensor_device_id or '(not configured)'}
  Table: {self.config.yolink.table_name}

S3 Configuration:
  Bucket: {self.config.s3.bucket}
  JSON Key: {self.config.s3.json_key}
  Backup Prefix: {self.config.s3.backup_prefix}

Backup Configuration:
  Day of Month: {self.config.backup.day_of_month}
  Hour: {self.config.backup.hour}:00

This notification confirms that Data Sleigh started successfully with the
configuration values shown above (including any environment variable overrides).

This is an automated notification.
"""

        if self.alert_manager:
            self.alert_manager._send_alert(subject, body)
            logger.info("Startup notification email sent")

    def _flush_loop(self) -> None:
        """Background thread to periodically flush database."""
        while self._running:
            time.sleep(self.config.database.flush_interval)
            if self.store and self._running:
                try:
                    self.store.flush()

                    # Run alert checks after flush
                    if self.alert_manager:
                        self.alert_manager.check_all(self.config.database.path)
                except Exception as e:
                    logger.error(f"Error during periodic flush: {e}")

    def _upload_loop(self) -> None:
        """Background thread for S3 uploads - only during season."""
        upload_count = 0
        first_upload = True

        while self._running:
            try:
                if self.is_in_season():
                    upload_count += 1

                    if first_upload:
                        logger.info(f"[IN-SEASON] Starting upload #{upload_count}")

                    # Query raw data
                    measurements = query_water_levels(
                        self.store.get_connection(),
                        minutes=self.config.upload.minutes_of_data,
                    )

                    # Query aggregated data
                    agg_1m = query_aggregated_data(
                        self.store.get_connection(), interval_minutes=1, lookback_hours=1
                    )
                    agg_5m = query_aggregated_data(
                        self.store.get_connection(),
                        interval_minutes=5,
                        lookback_hours=24,
                    )
                    agg_1h = query_aggregated_data(
                        self.store.get_connection(), interval_minutes=60, lookback_hours=None
                    )

                    # Query YoLink aggregated data
                    yolink_1m = query_yolink_aggregated_data(
                        self.store.get_connection(), interval_minutes=1, lookback_hours=1
                    )
                    yolink_5m = query_yolink_aggregated_data(
                        self.store.get_connection(), interval_minutes=5, lookback_hours=24
                    )
                    yolink_1h = query_yolink_aggregated_data(
                        self.store.get_connection(),
                        interval_minutes=60,
                        lookback_hours=None,
                    )

                    # Perform segment analysis periodically
                    if first_upload or (upload_count % 10 == 0):
                        analysis = analyze_water_level_segments(
                            self.store.get_connection()
                        )
                        if analysis:
                            self._cached_analysis = analysis

                    # Create JSON output with season information
                    output_data = create_json_output(
                        measurements,
                        season_start=self.config.season.start.isoformat(),
                        season_end=self.config.season.end.isoformat(),
                        is_in_season=True,
                        aggregates_1m=agg_1m,
                        aggregates_5m=agg_5m,
                        aggregates_1h=agg_1h,
                        analysis=self._cached_analysis,
                        yolink_1m=yolink_1m,
                        yolink_5m=yolink_5m,
                        yolink_1h=yolink_1h,
                        replay_delay=self.config.upload.replay_delay_seconds,
                    )

                    # Upload to S3
                    upload_to_s3(
                        data=output_data,
                        bucket=self.config.s3.bucket,
                        key=self.config.s3.json_key,
                        aws_access_key=self.config.s3.aws_access_key_id,
                        aws_secret_key=self.config.s3.aws_secret_access_key,
                        verbose=first_upload,
                    )

                    if first_upload:
                        logger.info("✓ First upload successful!")
                        logger.info(
                            "  Continuing uploads silently every "
                            f"{self.config.upload.interval_seconds}s"
                        )
                        first_upload = False

                else:
                    # Off-season: no uploads
                    if first_upload or upload_count % 100 == 0:
                        logger.info(
                            "[OFF-SEASON] Skipping JSON upload (season: "
                            f"{self.config.season.start} to {self.config.season.end})"
                        )

            except Exception as e:
                logger.error(f"Error during upload cycle: {e}")

            # Sleep until next upload cycle
            if self._running:
                time.sleep(self.config.upload.interval_seconds)

    def _backup_loop(self) -> None:
        """Background thread for monthly backups - only during off-season."""
        while self._running:
            try:
                # Only backup during off-season
                if not self.is_in_season():
                    if self.backup_manager and self.backup_manager.should_backup():
                        logger.info("Starting monthly backup...")
                        db_path = Path(self.config.database.path)
                        self.backup_manager.backup_database(db_path, self.store)

                        # Reinitialize storage with fresh database
                        self._initialize_storage()
                        logger.info("Storage reinitialized with fresh database")

            except Exception as e:
                logger.error(f"Error during backup cycle: {e}")

            # Check hourly
            if self._running:
                time.sleep(3600)

    def run(self) -> None:
        """Run the application.

        This method blocks until the application is shut down.
        """
        try:
            self._running = True
            self._setup_signal_handlers()

            # Initialize components
            logger.info("Initializing storage...")
            self._initialize_storage()

            logger.info("Initializing MQTT client...")
            self._initialize_mqtt()

            logger.info("Initializing alerting...")
            self._initialize_alerting()

            logger.info("Initializing YoLink client...")
            self._initialize_yolink()

            logger.info("Initializing backup manager...")
            self._initialize_backup()

            # Send startup notification email
            self._send_startup_notification()

            # Start background threads
            flush_thread = threading.Thread(
                target=self._flush_loop,
                daemon=True,
                name="FlushThread",
            )
            flush_thread.start()

            upload_thread = threading.Thread(
                target=self._upload_loop,
                daemon=True,
                name="UploadThread",
            )
            upload_thread.start()

            backup_thread = threading.Thread(
                target=self._backup_loop,
                daemon=True,
                name="BackupThread",
            )
            backup_thread.start()

            # Start YoLink client if configured
            if self.yolink_client:
                self.yolink_client.start()

            # Connect to MQTT broker
            if self.mqtt_client:
                self.mqtt_client.connect()

                in_season = self.is_in_season()
                logger.info("=" * 60)
                logger.info(f"🎄 Data Sleigh is running ({'IN-SEASON' if in_season else 'OFF-SEASON'})")
                logger.info("=" * 60)
                if in_season:
                    logger.info(
                        f"✓ Uploading JSON to S3 every {self.config.upload.interval_seconds}s"
                    )
                else:
                    logger.info("✓ Collecting data (no JSON uploads during off-season)")
                    logger.info("✓ Monthly database backups enabled")
                logger.info("Press Ctrl+C to stop.")
                logger.info("=" * 60)

                # Run MQTT loop (blocking)
                self.mqtt_client.loop_forever()

            # Wait for shutdown
            self._shutdown_event.wait()

        except Exception as e:
            logger.error(f"Application error: {e}", exc_info=True)
            sys.exit(1)
        finally:
            self._cleanup()

    def shutdown(self) -> None:
        """Initiate graceful shutdown."""
        if not self._running:
            return

        logger.info("Shutting down...")
        self._running = False

        # Disconnect MQTT
        if self.mqtt_client:
            try:
                self.mqtt_client.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting MQTT: {e}")

        # Stop YoLink client
        if self.yolink_client:
            try:
                self.yolink_client.stop()
            except Exception as e:
                logger.error(f"Error stopping YoLink client: {e}")

        self._shutdown_event.set()

    def _cleanup(self) -> None:
        """Cleanup resources."""
        logger.info("Cleaning up resources...")

        # Close database
        if self.store:
            try:
                self.store.close()
            except Exception as e:
                logger.error(f"Error closing database: {e}")

        logger.info("Shutdown complete")


def main(config_path: str | None = None) -> None:
    """Main entry point.

    Args:
        config_path: Optional path to config file (default: config/data_sleigh.toml)
    """
    if config_path is None:
        config_path = "config/data_sleigh.toml"

    try:
        app = DataSleighApp(config_path)
        app.run()
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        print(
            "Please create a configuration file. "
            "See config/data_sleigh.example.toml for an example.",
            file=sys.stderr,
        )
        sys.exit(1)
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        sys.exit(1)


