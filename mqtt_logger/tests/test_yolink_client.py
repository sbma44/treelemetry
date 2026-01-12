"""Tests for YoLink client module."""

from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from src.mqtt_logger.config import YoLinkConfig
from src.mqtt_logger.yolink_client import YoLinkAuthManager, YoLinkClient


@pytest.fixture
def yolink_config():
    """Create a test YoLink configuration."""
    return YoLinkConfig(
        enabled=True,
        uaid="test_uaid",
        secret_key="test_secret",
        air_sensor_device_id="d88b4c04000a9da6",
        water_sensor_device_id="d88b4c010008bbe2",
        table_name="yolink_sensors",
        reconnect_delay=5,
        max_reconnect_delay=300,
    )


@pytest.fixture
def sensor_callback():
    """Create a mock sensor callback."""
    return Mock()


def test_yolink_client_init(yolink_config, sensor_callback):
    """Test YoLinkClient initialization."""
    client = YoLinkClient(yolink_config, sensor_callback)

    assert client.config == yolink_config
    assert client.sensor_callback == sensor_callback
    assert not client._connected
    assert not client._should_run
    # Should have both device IDs mapped
    assert len(client._device_ids) == 2
    assert client._device_ids["d88b4c04000a9da6"] == "air"
    assert client._device_ids["d88b4c010008bbe2"] == "water"


def test_yolink_client_init_air_only(sensor_callback):
    """Test YoLinkClient with only air sensor configured."""
    config = YoLinkConfig(
        enabled=True,
        uaid="test_uaid",
        secret_key="test_secret",
        air_sensor_device_id="d88b4c04000a9da6",
        water_sensor_device_id=None,
    )
    client = YoLinkClient(config, sensor_callback)

    assert len(client._device_ids) == 1
    assert client._device_ids["d88b4c04000a9da6"] == "air"


def test_yolink_client_init_water_only(sensor_callback):
    """Test YoLinkClient with only water sensor configured."""
    config = YoLinkConfig(
        enabled=True,
        uaid="test_uaid",
        secret_key="test_secret",
        air_sensor_device_id=None,
        water_sensor_device_id="d88b4c010008bbe2",
    )
    client = YoLinkClient(config, sensor_callback)

    assert len(client._device_ids) == 1
    assert client._device_ids["d88b4c010008bbe2"] == "water"


def test_process_message_air_sensor(yolink_config, sensor_callback):
    """Test _process_message for air sensor."""
    client = YoLinkClient(yolink_config, sensor_callback)

    # Air sensor payload (from user's example)
    air_sensor_payload = {
        "event": "THSensor.Report",
        "time": 1765471082363,
        "msgid": "1765471082362",
        "data": {
            "state": "normal",
            "alarm": {
                "lowBattery": False,
                "lowTemp": False,
                "highTemp": False,
                "lowHumidity": False,
                "highHumidity": False,
                "period": False,
                "code": 0,
            },
            "battery": 4,
            "mode": "f",
            "interval": 0,
            "temperature": 21.7,
            "humidity": 37,
            "tempLimit": {"max": 35, "min": 18},
            "humidityLimit": {"max": 100, "min": 0},
            "tempCorrection": 0,
            "humidityCorrection": 0,
            "version": "039f",
            "loraInfo": {
                "netId": "010203",
                "devNetType": "A",
                "signal": -33,
                "gatewayId": "d88b4c1603047f3a",
                "gateways": 2,
            },
        },
        "deviceId": "d88b4c04000a9da6",
    }

    # Process the message
    client._process_message("d88b4c04000a9da6", air_sensor_payload)

    # Verify callback was called correctly
    sensor_callback.assert_called_once_with(
        "air",  # device_type
        21.7,  # temperature
        37,  # humidity (included for air sensor)
        "d88b4c04000a9da6",  # device_id
        air_sensor_payload,  # raw_data
    )


def test_process_message_water_sensor(yolink_config, sensor_callback):
    """Test _process_message for water sensor."""
    client = YoLinkClient(yolink_config, sensor_callback)

    # Water sensor payload (from user's example)
    water_sensor_payload = {
        "event": "THSensor.Report",
        "time": 1765468644065,
        "msgid": "1765468644064",
        "data": {
            "state": "normal",
            "alarm": {
                "lowBattery": False,
                "lowTemp": False,
                "highTemp": False,
                "lowHumidity": False,
                "highHumidity": False,
                "period": False,
                "code": 0,
            },
            "battery": 4,
            "mode": "f",
            "interval": 0,
            "temperature": 16.3,
            "humidity": 0,  # Always 0 for water sensor
            "tempLimit": {"max": 32.2, "min": 4.4},
            "humidityLimit": {"max": 0, "min": 0},
            "tempCorrection": 0,
            "humidityCorrection": 0,
            "version": "0412",
            "batteryType": "Li",
            "loraInfo": {
                "netId": "010203",
                "devNetType": "A",
                "signal": -55,
                "gatewayId": "d88b4c1603047f3a",
                "gateways": 1,
            },
        },
        "deviceId": "d88b4c010008bbe2",
    }

    # Process the message
    client._process_message("d88b4c010008bbe2", water_sensor_payload)

    # Verify callback was called - humidity should be None for water sensor
    sensor_callback.assert_called_once_with(
        "water",  # device_type
        16.3,  # temperature
        None,  # humidity (ignored for water sensor)
        "d88b4c010008bbe2",  # device_id
        water_sensor_payload,  # raw_data
    )


def test_process_message_unknown_device(yolink_config, sensor_callback):
    """Test _process_message ignores unknown devices."""
    client = YoLinkClient(yolink_config, sensor_callback)

    # Message from an unknown device
    unknown_payload = {
        "event": "THSensor.Report",
        "time": 1765468644065,
        "data": {"temperature": 25.0, "humidity": 50},
        "deviceId": "unknown_device_id",
    }

    # Process the message
    client._process_message("unknown_device_id", unknown_payload)

    # Callback should NOT be called for unknown devices
    sensor_callback.assert_not_called()


def test_process_message_non_report_event(yolink_config, sensor_callback):
    """Test _process_message ignores non-report events."""
    client = YoLinkClient(yolink_config, sensor_callback)

    # Non-report event (e.g., status change)
    status_payload = {
        "event": "THSensor.StatusChange",
        "time": 1765468644065,
        "data": {"state": "online"},
        "deviceId": "d88b4c04000a9da6",
    }

    # Process the message
    client._process_message("d88b4c04000a9da6", status_payload)

    # Callback should NOT be called for non-report events
    sensor_callback.assert_not_called()


def test_process_message_missing_temperature(yolink_config, sensor_callback):
    """Test _process_message handles missing temperature gracefully."""
    client = YoLinkClient(yolink_config, sensor_callback)

    # Payload missing temperature
    bad_payload = {
        "event": "THSensor.Report",
        "time": 1765468644065,
        "data": {"humidity": 50},  # No temperature
        "deviceId": "d88b4c04000a9da6",
    }

    # Process the message
    client._process_message("d88b4c04000a9da6", bad_payload)

    # Callback should NOT be called when temperature is missing
    sensor_callback.assert_not_called()


def test_start_disabled(yolink_config, sensor_callback):
    """Test start does nothing when disabled."""
    config = YoLinkConfig(
        enabled=False,
        uaid="test_uaid",
        secret_key="test_secret",
    )
    client = YoLinkClient(config, sensor_callback)

    client.start()

    assert not client._should_run
    assert client._thread is None


def test_start_no_credentials(sensor_callback):
    """Test start does nothing without credentials."""
    config = YoLinkConfig(
        enabled=True,
        uaid=None,
        secret_key=None,
    )
    client = YoLinkClient(config, sensor_callback)

    client.start()

    assert not client._should_run
    assert client._thread is None


def test_start_no_device_ids(sensor_callback):
    """Test start does nothing without device IDs."""
    config = YoLinkConfig(
        enabled=True,
        uaid="test_uaid",
        secret_key="test_secret",
        air_sensor_device_id=None,
        water_sensor_device_id=None,
    )
    client = YoLinkClient(config, sensor_callback)

    client.start()

    assert not client._should_run
    assert client._thread is None


def test_stop_not_running(yolink_config, sensor_callback):
    """Test stop gracefully handles not running."""
    client = YoLinkClient(yolink_config, sensor_callback)

    # Should not raise exception
    client.stop()

    assert not client._should_run


def test_connected_property(yolink_config, sensor_callback):
    """Test connected property."""
    client = YoLinkClient(yolink_config, sensor_callback)

    assert not client.connected

    client._connected = True
    assert client.connected


def test_reconnect_delay_reset(yolink_config, sensor_callback):
    """Test that reconnect delay can be reset."""
    client = YoLinkClient(yolink_config, sensor_callback)

    # Simulate multiple failed reconnection attempts
    client._current_reconnect_delay = 160  # Already backed off

    # Reset to initial value (happens on successful connection)
    client._current_reconnect_delay = yolink_config.reconnect_delay

    # Verify it was reset
    assert client._current_reconnect_delay == yolink_config.reconnect_delay


class TestYoLinkAuthManager:
    """Tests for YoLinkAuthManager class."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock aiohttp session."""
        return MagicMock()

    def test_access_token_empty_initially(self, mock_session):
        """Test that access_token returns empty string initially."""
        auth_mgr = YoLinkAuthManager(mock_session, "uaid", "secret")
        assert auth_mgr.access_token() == ""

    def test_access_token_after_set(self, mock_session):
        """Test that access_token returns the token after it's set."""
        auth_mgr = YoLinkAuthManager(mock_session, "uaid", "secret")
        auth_mgr._access_token = "test_token"
        assert auth_mgr.access_token() == "test_token"

    @pytest.mark.asyncio
    async def test_check_and_refresh_token_fetches_when_none(self, mock_session):
        """Test that check_and_refresh_token fetches token when none exists."""
        auth_mgr = YoLinkAuthManager(mock_session, "uaid", "secret")

        # Mock the _fetch_token method
        auth_mgr._fetch_token = AsyncMock()
        auth_mgr._access_token = "new_token"

        result = await auth_mgr.check_and_refresh_token()

        auth_mgr._fetch_token.assert_called_once()
        assert result == "new_token"

    @pytest.mark.asyncio
    async def test_fetch_token_makes_correct_request(self):
        """Test that _fetch_token makes the correct OAuth2 request."""
        # Create a mock response
        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(
            return_value={
                "access_token": "test_token_123",
                "expires_in": 7200,
            }
        )

        # Create a mock context manager for the post request
        mock_post_cm = AsyncMock()
        mock_post_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_post_cm.__aexit__ = AsyncMock(return_value=None)

        # Create mock session
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_post_cm)

        auth_mgr = YoLinkAuthManager(mock_session, "test_uaid", "test_secret")

        await auth_mgr._fetch_token()

        # Verify the token was set
        assert auth_mgr._access_token == "test_token_123"
        assert auth_mgr._token_expires_at is not None

        # Verify post was called with correct parameters
        mock_session.post.assert_called_once()
        call_args = mock_session.post.call_args
        assert "grant_type" in str(call_args)
        assert "client_credentials" in str(call_args)




