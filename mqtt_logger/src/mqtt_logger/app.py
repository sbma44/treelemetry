"""Main application logic for MQTT Logger."""

import logging
import signal
import sys
import threading
import time
from pathlib import Path

from .alerting import AlertManager
from .config import Config, load_config
from .mqtt_client import MQTTLogger
from .storage import MessageStore

logger = logging.getLogger(__name__)


class MQTTLoggerApp:
    """Main application for logging MQTT messages to DuckDB.

    Manages the lifecycle of MQTT connections and database storage,
    handles graceful shutdown, and coordinates message routing.

    Example:
        >>> app = MQTTLoggerApp("config/mqtt_logger.toml")
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
        self._running = False
        self._shutdown_event = threading.Event()

        # Map topics to table names
        self._topic_table_map: dict[str, str] = {}

        logger.info("MQTT Logger application initialized")

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
                self.store.insert_message(
                    table_name, topic, payload, qos, retain
                )
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
        for topic_part, pattern_part in zip(topic_parts, pattern_parts):
            if pattern_part != "+" and pattern_part != topic_part:
                return False

        return True

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

    def _send_startup_notification(self) -> None:
        """Send startup success email notification."""
        if not self.config.alerting.email_to:
            return

        import socket
        from datetime import datetime

        hostname = socket.gethostname()
        start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z")

        # Format topics list
        topics_list = "\n".join([
            f"  • {t.pattern} → {t.table_name}" +
            (f" ({t.description})" if t.description else "")
            for t in self.config.topics
        ])

        subject = "MQTT Logger Started Successfully"
        body = f"""MQTT Logger has started successfully!

Container: {hostname}
Start Time: {start_time}

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

This notification confirms that MQTT Logger started successfully with the
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

            # Send startup notification email
            self._send_startup_notification()

            # Start periodic flush thread
            flush_thread = threading.Thread(
                target=self._flush_loop,
                daemon=True,
                name="FlushThread",
            )
            flush_thread.start()

            # Connect to MQTT broker
            if self.mqtt_client:
                self.mqtt_client.connect()

                logger.info("MQTT Logger is running. Press Ctrl+C to stop.")

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
        config_path: Optional path to config file (default: config/mqtt_logger.toml)
    """
    if config_path is None:
        config_path = "config/mqtt_logger.toml"

    try:
        app = MQTTLoggerApp(config_path)
        app.run()
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        print(
            "Please create a configuration file. "
            "See config/mqtt_logger.example.toml for an example.",
            file=sys.stderr,
        )
        sys.exit(1)
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        sys.exit(1)

