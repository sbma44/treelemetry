"""YoLink MQTT client for receiving sensor data from YoLink devices.

This module provides integration with YoLink's MQTT service using the yolink-api
library to receive real-time sensor data from air and water temperature sensors.
"""

import asyncio
import json
import logging
import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import aiohttp
import aiomqtt
from yolink.auth_mgr import YoLinkAuthMgr
from yolink.client import YoLinkClient as YoLinkAPIClient
from yolink.const import OAUTH2_TOKEN
from yolink.endpoint import Endpoints

from .config import YoLinkConfig

logger = logging.getLogger(__name__)


class YoLinkAuthManager(YoLinkAuthMgr):
    """Authentication manager for YoLink API using OAuth2 client credentials.

    Handles token acquisition and refresh using UAID and Secret Key.
    """

    def __init__(
        self, session: aiohttp.ClientSession, uaid: str, secret_key: str
    ) -> None:
        """Initialize the auth manager.

        Args:
            session: An aiohttp ClientSession for making HTTP requests
            uaid: YoLink User Access ID
            secret_key: YoLink Secret Key
        """
        super().__init__(session)
        self._uaid = uaid
        self._secret_key = secret_key
        self._access_token: str | None = None
        self._token_expires_at: datetime | None = None

    def access_token(self) -> str:
        """Return the current access token."""
        return self._access_token or ""

    async def check_and_refresh_token(self) -> str:
        """Check if token is valid and refresh if necessary.

        Returns:
            The current valid access token
        """
        # Refresh if no token or token expires within 5 minutes
        if (
            self._access_token is None
            or self._token_expires_at is None
            or datetime.now(UTC)
            >= self._token_expires_at - timedelta(minutes=5)
        ):
            await self._fetch_token()
        return self._access_token

    async def _fetch_token(self) -> None:
        """Fetch a new access token from YoLink OAuth2 endpoint."""
        logger.debug("Fetching new YoLink access token...")
        async with self._session.post(
            OAUTH2_TOKEN,
            data={
                "grant_type": "client_credentials",
                "client_id": self._uaid,
                "client_secret": self._secret_key,
            },
        ) as response:
            response.raise_for_status()
            data = await response.json()

            self._access_token = data["access_token"]
            # Token typically expires in 7200 seconds (2 hours)
            expires_in = data.get("expires_in", 7200)
            self._token_expires_at = datetime.now(UTC) + timedelta(
                seconds=expires_in
            )
            logger.info(
                f"YoLink token acquired, expires in {expires_in}s"
            )


class YoLinkClient:
    """MQTT client for YoLink device communication using yolink-api library.

    Connects to YoLink's MQTT broker and receives sensor reports from
    configured air and water temperature sensors.

    Features:
    - Token-based authentication via yolink-api
    - Automatic reconnection with exponential backoff
    - Device ID filtering to process only configured sensors
    - Separate handling for air sensor (temp + humidity) and water sensor (temp only)

    Example:
        >>> def on_sensor_data(device_type, temperature, humidity, device_id, raw_data):
        ...     print(f"{device_type}: temp={temperature}, humidity={humidity}")
        >>>
        >>> client = YoLinkClient(config, on_sensor_data)
        >>> client.start()
    """

    def __init__(
        self,
        config: YoLinkConfig,
        sensor_callback: Callable[[str, float, float | None, str, dict], None],
    ):
        """Initialize the YoLink client.

        Args:
            config: YoLink configuration
            sensor_callback: Function called for each sensor reading.
                Signature: callback(device_type, temperature, humidity, device_id, raw_data)
                - device_type: "air" or "water"
                - temperature: Temperature reading (float)
                - humidity: Humidity reading (float) or None for water sensor
                - device_id: The device ID that reported the data
                - raw_data: The complete raw message data dict
        """
        self.config = config
        self.sensor_callback = sensor_callback
        self._should_run = False
        self._connected = False
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._current_reconnect_delay = config.reconnect_delay

        # Build device ID lookup for efficient filtering
        self._device_ids: dict[str, str] = {}
        if config.air_sensor_device_id:
            self._device_ids[config.air_sensor_device_id] = "air"
        if config.water_sensor_device_id:
            self._device_ids[config.water_sensor_device_id] = "water"

        logger.info(
            f"YoLink client initialized with {len(self._device_ids)} device(s): "
            f"air={config.air_sensor_device_id}, water={config.water_sensor_device_id}"
        )

    def _process_message(self, device_id: str, payload: dict) -> None:
        """Process an incoming MQTT message.

        Args:
            device_id: The device ID from the topic
            payload: Parsed JSON payload
        """
        logger.info(
            f"_process_message called: device_id={device_id}, "
            f"configured_devices={list(self._device_ids.keys())}"
        )

        # Filter: only process messages from our configured devices
        if device_id not in self._device_ids:
            logger.info(
                f"Ignoring message from untracked device: {device_id} "
                f"(not in {list(self._device_ids.keys())})"
            )
            return

        device_type = self._device_ids[device_id]
        event = payload.get("event", "")
        logger.info(f"Processing {device_type} sensor event: {event}")

        # Only process THSensor.Report events
        if event != "THSensor.Report":
            logger.info(f"Ignoring non-report event: {event} (expected THSensor.Report)")
            return

        data = payload.get("data", {})
        temperature = data.get("temperature")

        if temperature is None:
            logger.warning(f"No temperature in report from {device_id}")
            return

        # For air sensor, include humidity; for water sensor, ignore it (always 0)
        humidity = None
        if device_type == "air":
            humidity = data.get("humidity")

        logger.info(
            f"YoLink {device_type} sensor ({device_id}): "
            f"temp={temperature}°F, humidity={humidity}%"
        )

        # Call the callback with parsed data
        logger.info(f"Calling sensor_callback for {device_type} sensor")
        self.sensor_callback(
            device_type,
            temperature,
            humidity,
            device_id,
            payload,
        )
        logger.info(f"sensor_callback completed for {device_type} sensor")

    async def _run_async(self) -> None:
        """Main async loop for MQTT connection with reconnection handling."""
        logger.info(
            f"YoLink async loop starting, should_run={self._should_run}, "
            f"configured devices: air={self.config.air_sensor_device_id}, "
            f"water={self.config.water_sensor_device_id}"
        )
        while self._should_run:
            try:
                logger.info("Creating aiohttp session for YoLink...")
                async with aiohttp.ClientSession() as session:
                    # Create auth manager and client
                    auth_mgr = YoLinkAuthManager(
                        session,
                        self.config.uaid,
                        self.config.secret_key,
                    )
                    api_client = YoLinkAPIClient(auth_mgr)

                    # Authenticate
                    logger.info("Authenticating with YoLink API...")
                    await auth_mgr.check_and_refresh_token()
                    logger.info("YoLink authentication successful")

                    # Get home ID (required for MQTT topic subscription)
                    logger.info("Retrieving YoLink home information...")
                    home_response = await api_client.execute(
                        url=Endpoints.US.value.url,
                        bsdp={"method": "Home.getGeneralInfo"},
                    )
                    home_id = home_response.data.get("id")
                    home_name = home_response.data.get("name", "Unknown")
                    logger.info(f"YoLink home: {home_name} (ID: {home_id})")

                    # Build MQTT topic
                    # Format: yl-home/{home_id}/+/report
                    mqtt_topic = f"yl-home/{home_id}/+/report"

                    # Get broker details from endpoints
                    broker_host = Endpoints.US.value.mqtt_broker_host
                    broker_port = Endpoints.US.value.mqtt_broker_port

                    logger.info(
                        f"Connecting to YoLink MQTT broker at "
                        f"{broker_host}:{broker_port}"
                    )
                    logger.info(f"Subscribing to topic: {mqtt_topic}")

                    # Connect to MQTT broker
                    logger.info(
                        f"Attempting MQTT connection: host={broker_host}, "
                        f"port={broker_port}, username_len={len(auth_mgr.access_token())}"
                    )
                    async with aiomqtt.Client(
                        hostname=broker_host,
                        port=broker_port,
                        username=auth_mgr.access_token(),
                        password="",  # Password not used, only token as username
                        keepalive=60,
                    ) as mqtt_client:
                        self._connected = True
                        self._current_reconnect_delay = self.config.reconnect_delay
                        logger.info("Connected to YoLink MQTT broker successfully")

                        logger.info(f"Subscribing to MQTT topic: {mqtt_topic}")
                        await mqtt_client.subscribe(mqtt_topic)
                        logger.info(f"Subscribed to YoLink topic: {mqtt_topic}")

                        # Process incoming messages
                        logger.info("Entering YoLink message loop, waiting for events...")
                        async for message in mqtt_client.messages:
                            # Log EVERY message received
                            logger.info(
                                f"YoLink MQTT message received: "
                                f"topic={message.topic}, "
                                f"payload_len={len(message.payload)} bytes"
                            )
                            logger.debug(
                                f"YoLink MQTT raw payload: {message.payload[:500]}"
                            )

                            if not self._should_run:
                                logger.info("YoLink client stopping, exiting message loop")
                                break

                            try:
                                # Parse topic to extract device ID
                                # Format: yl-home/{home_id}/{device_id}/report
                                topic_parts = str(message.topic).split("/")
                                logger.debug(f"YoLink topic parts: {topic_parts}")
                                device_id = (
                                    topic_parts[2]
                                    if len(topic_parts) >= 4
                                    else "unknown"
                                )
                                logger.info(f"YoLink message from device_id={device_id}")

                                # Parse payload
                                payload = json.loads(
                                    message.payload.decode("utf-8")
                                )
                                event_type = payload.get("event", "unknown")
                                payload_device_id = payload.get("deviceId", "unknown")
                                logger.info(
                                    f"YoLink event: type={event_type}, "
                                    f"payload_device_id={payload_device_id}"
                                )

                                # Process the message
                                self._process_message(device_id, payload)

                            except json.JSONDecodeError as e:
                                logger.error(
                                    f"Failed to parse YoLink message: {e}, "
                                    f"raw={message.payload[:200]}"
                                )
                            except Exception as e:
                                logger.error(
                                    f"Error processing YoLink message: {e}",
                                    exc_info=True,
                                )

            except aiomqtt.MqttError as e:
                self._connected = False
                logger.error(f"YoLink MQTT error: {e}")
            except aiohttp.ClientError as e:
                self._connected = False
                logger.error(f"YoLink HTTP error: {e}")
            except Exception as e:
                self._connected = False
                logger.error(f"YoLink connection error: {e}", exc_info=True)

            # If we should continue running, wait before reconnecting
            if self._should_run:
                logger.info(
                    f"Reconnecting to YoLink in {self._current_reconnect_delay}s..."
                )
                await asyncio.sleep(self._current_reconnect_delay)

                # Exponential backoff
                self._current_reconnect_delay = min(
                    self._current_reconnect_delay * 2,
                    self.config.max_reconnect_delay,
                )

        self._connected = False
        logger.info("YoLink async loop ended")

    def _run_loop(self) -> None:
        """Run the async event loop in a thread."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._run_async())
        finally:
            self._loop.close()
            self._loop = None

    def start(self) -> None:
        """Start the YoLink client in a background thread."""
        if not self.config.enabled:
            logger.info("YoLink integration is disabled")
            return

        if not self.config.uaid or not self.config.secret_key:
            logger.warning("YoLink credentials not configured, skipping")
            return

        if not self._device_ids:
            logger.warning("No YoLink device IDs configured, skipping")
            return

        self._should_run = True
        self._thread = threading.Thread(
            target=self._run_loop,
            daemon=True,
            name="YoLinkClient",
        )
        self._thread.start()
        logger.info("YoLink client started")

    def stop(self) -> None:
        """Stop the YoLink client gracefully."""
        logger.info("Stopping YoLink client...")
        self._should_run = False

        # Cancel any pending tasks in the event loop
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)

        self._connected = False
        logger.info("YoLink client stopped")

    @property
    def connected(self) -> bool:
        """Return whether the client is currently connected."""
        return self._connected




