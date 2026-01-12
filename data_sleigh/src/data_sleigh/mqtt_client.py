"""MQTT client with automatic reconnection and message handling."""

import logging
import time
from typing import Callable

import paho.mqtt.client as mqtt

from .config import MQTTConfig

logger = logging.getLogger(__name__)


class MQTTLogger:
    """MQTT client that logs messages to a storage backend.
    
    Features:
    - Automatic reconnection on connection loss
    - Configurable QoS levels
    - Support for multiple topic subscriptions
    - Callback-based message handling
    
    Example:
        >>> def handle_message(topic, payload, qos, retain):
        ...     print(f"Received: {topic} = {payload}")
        >>> 
        >>> client = MQTTLogger(mqtt_config, handle_message)
        >>> client.subscribe("sensor/#")
        >>> client.connect()
        >>> client.loop_forever()
    """
    
    def __init__(
        self,
        config: MQTTConfig,
        message_callback: Callable[[str, bytes, int, bool], None],
    ):
        """Initialize the MQTT logger.
        
        Args:
            config: MQTT configuration
            message_callback: Function called for each received message
                Signature: callback(topic: str, payload: bytes, qos: int, retain: bool)
        """
        self.config = config
        self.message_callback = message_callback
        self._subscriptions: list[tuple[str, int]] = []
        self._connected = False
        self._should_reconnect = True
        
        # Create MQTT client
        client_id = config.client_id or f"mqtt_logger_{int(time.time())}"
        self._client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=client_id,
        )
        
        # Set authentication if provided
        if config.username:
            self._client.username_pw_set(config.username, config.password)
        
        # Set callbacks
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message
        
        logger.info(f"MQTT client initialized: {client_id}")
    
    def subscribe(self, topic: str, qos: int | None = None) -> None:
        """Add a topic subscription.
        
        Args:
            topic: MQTT topic pattern (can include wildcards + and #)
            qos: Quality of Service level (uses config default if not provided)
        """
        qos = qos if qos is not None else self.config.qos
        self._subscriptions.append((topic, qos))
        
        # Subscribe immediately if already connected
        if self._connected:
            result = self._client.subscribe(topic, qos)
            if result[0] == mqtt.MQTT_ERR_SUCCESS:
                logger.info(f"Subscribed to topic: {topic} (QoS {qos})")
            else:
                logger.error(f"Failed to subscribe to {topic}: {result}")
    
    def connect(self) -> None:
        """Connect to the MQTT broker.
        
        Raises:
            Exception: If connection fails
        """
        try:
            logger.info(
                f"Connecting to MQTT broker at {self.config.broker}:{self.config.port}"
            )
            self._client.connect(
                self.config.broker,
                self.config.port,
                self.config.keepalive,
            )
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")
            raise
    
    def disconnect(self) -> None:
        """Disconnect from the MQTT broker."""
        self._should_reconnect = False
        self._client.disconnect()
        logger.info("Disconnected from MQTT broker")
    
    def loop_forever(self) -> None:
        """Run the MQTT client loop (blocking).
        
        This method will block until disconnect() is called or an
        unrecoverable error occurs.
        """
        try:
            self._client.loop_forever()
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
            self.disconnect()
        except Exception as e:
            logger.error(f"MQTT loop error: {e}")
            raise
    
    def loop_start(self) -> None:
        """Start the MQTT client loop in a background thread."""
        self._client.loop_start()
    
    def loop_stop(self) -> None:
        """Stop the background MQTT client loop."""
        self._client.loop_stop()
    
    def _on_connect(
        self,
        client: mqtt.Client,
        userdata: any,
        flags: mqtt.ConnectFlags,
        reason_code: mqtt.ReasonCode,
        properties: mqtt.Properties | None = None,
    ) -> None:
        """Callback for successful connection."""
        if reason_code == 0:
            self._connected = True
            logger.info("Connected to MQTT broker")
            
            # Subscribe to all topics
            for topic, qos in self._subscriptions:
                result = self._client.subscribe(topic, qos)
                if result[0] == mqtt.MQTT_ERR_SUCCESS:
                    logger.info(f"Subscribed to topic: {topic} (QoS {qos})")
                else:
                    logger.error(f"Failed to subscribe to {topic}: {result}")
        else:
            logger.error(f"Connection failed with reason code: {reason_code}")
    
    def _on_disconnect(
        self,
        client: mqtt.Client,
        userdata: any,
        flags: mqtt.DisconnectFlags,
        reason_code: mqtt.ReasonCode,
        properties: mqtt.Properties | None = None,
    ) -> None:
        """Callback for disconnection."""
        self._connected = False
        
        if reason_code == 0:
            logger.info("Cleanly disconnected from MQTT broker")
        else:
            logger.warning(
                f"Unexpectedly disconnected from MQTT broker (code: {reason_code})"
            )
            
            if self._should_reconnect:
                logger.info("Automatic reconnection will be attempted")
    
    def _on_message(
        self,
        client: mqtt.Client,
        userdata: any,
        message: mqtt.MQTTMessage,
    ) -> None:
        """Callback for received messages."""
        try:
            logger.debug(
                f"Received message on {message.topic} "
                f"(QoS {message.qos}, retain={message.retain})"
            )
            
            self.message_callback(
                message.topic,
                message.payload,
                message.qos,
                message.retain,
            )
        except Exception as e:
            logger.error(f"Error processing message on {message.topic}: {e}")

