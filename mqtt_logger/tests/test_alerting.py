"""Tests for alerting module."""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.mqtt_logger.alerting import AlertManager


@pytest.fixture
def temp_db_file():
    """Create a temporary database file."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
        # Write some data to give it size
        f.write(b"0" * (10 * 1024 * 1024))  # 10 MB
        db_path = Path(f.name)
    
    yield db_path
    
    db_path.unlink(missing_ok=True)


def test_alert_manager_disabled_by_default():
    """Test that alerting is disabled when no email is configured."""
    manager = AlertManager(
        email_to=None,
        db_size_threshold_mb=100,
        free_space_threshold_mb=100,
    )
    
    assert not manager.enabled


def test_alert_manager_enabled_with_email():
    """Test that alerting is enabled when email is configured."""
    manager = AlertManager(
        email_to="test@example.com",
        db_size_threshold_mb=100,
        free_space_threshold_mb=100,
    )
    
    assert manager.enabled
    assert manager.email_to == "test@example.com"


def test_check_db_size_no_alert_when_below_threshold(temp_db_file):
    """Test that no alert is sent when database is below threshold."""
    manager = AlertManager(
        email_to="test@example.com",
        db_size_threshold_mb=100,  # 100 MB threshold
        free_space_threshold_mb=None,
    )
    
    with patch.object(manager, "_send_alert") as mock_send:
        manager.check_db_size(temp_db_file)
        mock_send.assert_not_called()


def test_check_db_size_alert_when_above_threshold(temp_db_file):
    """Test that alert is sent when database exceeds threshold."""
    manager = AlertManager(
        email_to="test@example.com",
        db_size_threshold_mb=5,  # 5 MB threshold (file is 10 MB)
        free_space_threshold_mb=None,
    )
    
    with patch.object(manager, "_send_alert") as mock_send:
        manager.check_db_size(temp_db_file)
        mock_send.assert_called_once()
        
        # Check alert content
        args = mock_send.call_args
        assert "Database Size Alert" in args[1]["subject"]
        assert str(temp_db_file) in args[1]["body"]
        assert "5 MB" in args[1]["body"]


def test_check_db_size_respects_cooldown(temp_db_file):
    """Test that alerts respect cooldown period."""
    manager = AlertManager(
        email_to="test@example.com",
        db_size_threshold_mb=5,
        free_space_threshold_mb=None,
        alert_cooldown_hours=1,
    )
    
    with patch.object(manager, "_send_alert") as mock_send:
        # First check - should send alert
        manager.check_db_size(temp_db_file)
        assert mock_send.call_count == 1
        
        # Second check immediately - should NOT send (cooldown)
        manager.check_db_size(temp_db_file)
        assert mock_send.call_count == 1
        
        # Simulate time passing
        alert_key = f"db_size_{temp_db_file}"
        manager._last_alerts[alert_key] = datetime.now() - timedelta(hours=2)
        
        # Third check after cooldown - should send
        manager.check_db_size(temp_db_file)
        assert mock_send.call_count == 2


def test_check_db_size_disabled_when_threshold_none(temp_db_file):
    """Test that DB size check is disabled when threshold is None."""
    manager = AlertManager(
        email_to="test@example.com",
        db_size_threshold_mb=None,  # Disabled
        free_space_threshold_mb=None,
    )
    
    with patch.object(manager, "_send_alert") as mock_send:
        manager.check_db_size(temp_db_file)
        mock_send.assert_not_called()


def test_check_free_space_no_alert_when_sufficient(temp_db_file):
    """Test that no alert is sent when free space is sufficient."""
    manager = AlertManager(
        email_to="test@example.com",
        db_size_threshold_mb=None,
        free_space_threshold_mb=10,  # Very low threshold (10 MB)
    )
    
    with patch.object(manager, "_send_alert") as mock_send:
        manager.check_free_space(temp_db_file)
        mock_send.assert_not_called()


def test_check_free_space_alert_when_low():
    """Test that alert is sent when free space is low."""
    # Create a path in temp directory
    temp_path = Path(tempfile.gettempdir())
    
    manager = AlertManager(
        email_to="test@example.com",
        db_size_threshold_mb=None,
        free_space_threshold_mb=999999999,  # Very high threshold
    )
    
    with patch.object(manager, "_send_alert") as mock_send:
        manager.check_free_space(temp_path)
        
        # Should send alert since threshold is impossibly high
        mock_send.assert_called_once()
        args = mock_send.call_args
        assert "Low Disk Space Alert" in args[1]["subject"]
        assert str(temp_path) in args[1]["body"]


def test_check_free_space_disabled_when_threshold_none(temp_db_file):
    """Test that free space check is disabled when threshold is None."""
    manager = AlertManager(
        email_to="test@example.com",
        db_size_threshold_mb=None,
        free_space_threshold_mb=None,  # Disabled
    )
    
    with patch.object(manager, "_send_alert") as mock_send:
        manager.check_free_space(temp_db_file)
        mock_send.assert_not_called()


def test_check_all_runs_both_checks(temp_db_file):
    """Test that check_all runs all configured checks."""
    manager = AlertManager(
        email_to="test@example.com",
        db_size_threshold_mb=1,
        free_space_threshold_mb=999999999,
    )
    
    with patch.object(manager, "check_db_size") as mock_db:
        with patch.object(manager, "check_free_space") as mock_space:
            manager.check_all(temp_db_file)
            
            mock_db.assert_called_once_with(temp_db_file)
            mock_space.assert_called_once_with(temp_db_file)


def test_check_all_disabled_when_no_email(temp_db_file):
    """Test that check_all does nothing when alerting is disabled."""
    manager = AlertManager(
        email_to=None,
        db_size_threshold_mb=100,
        free_space_threshold_mb=100,
    )
    
    with patch.object(manager, "check_db_size") as mock_db:
        with patch.object(manager, "check_free_space") as mock_space:
            manager.check_all(temp_db_file)
            
            mock_db.assert_not_called()
            mock_space.assert_not_called()


@patch("os.path.exists")
@patch("subprocess.run")
@patch("subprocess.Popen")
def test_send_alert_calls_mail_command(mock_popen, mock_run, mock_exists):
    """Test that _send_alert calls msmtp correctly."""
    # Mock the version check to succeed
    mock_run.return_value = Mock()
    
    # Mock that msmtprc exists
    mock_exists.return_value = True
    
    mock_process = Mock()
    mock_process.communicate.return_value = ("", "")
    mock_process.returncode = 0
    mock_popen.return_value = mock_process
    
    manager = AlertManager(
        email_to="test@example.com",
        db_size_threshold_mb=100,
        free_space_threshold_mb=100,
    )
    
    manager._send_alert("Test Subject", "Test Body")
    
    # Verify msmtp was called with -C and -t flags
    assert mock_popen.call_count >= 1
    # Get the last call (the actual send, not version check)
    call_args = mock_popen.call_args
    cmd = call_args[0][0]
    assert cmd[0] in ["/usr/bin/msmtp", "/usr/local/bin/msmtp", "msmtp"]
    assert "-C" in cmd  # Config file flag
    assert "/root/.msmtprc" in cmd  # Config path
    assert "-t" in cmd  # Read recipients from message flag
    
    # Verify message was sent with proper headers
    communicate_call = mock_process.communicate.call_args
    message = communicate_call[1]["input"]
    assert "To: test@example.com" in message
    assert "Subject: Test Subject" in message
    assert "Test Body" in message


@patch("subprocess.Popen")
def test_send_alert_handles_mail_command_failure(mock_popen):
    """Test that _send_alert handles mail command failures gracefully."""
    mock_process = Mock()
    mock_process.communicate.return_value = ("", "Error message")
    mock_process.returncode = 1
    mock_popen.return_value = mock_process
    
    manager = AlertManager(
        email_to="test@example.com",
        db_size_threshold_mb=100,
        free_space_threshold_mb=100,
    )
    
    # Should not raise exception
    manager._send_alert("Test Subject", "Test Body")


@patch("subprocess.Popen")
def test_send_alert_handles_mail_command_not_found(mock_popen):
    """Test that _send_alert handles missing mail command gracefully."""
    mock_popen.side_effect = FileNotFoundError()
    
    manager = AlertManager(
        email_to="test@example.com",
        db_size_threshold_mb=100,
        free_space_threshold_mb=100,
    )
    
    # Should not raise exception
    manager._send_alert("Test Subject", "Test Body")


def test_check_db_size_handles_missing_file():
    """Test that check_db_size handles missing database file gracefully."""
    manager = AlertManager(
        email_to="test@example.com",
        db_size_threshold_mb=100,
        free_space_threshold_mb=None,
    )
    
    with patch.object(manager, "_send_alert") as mock_send:
        # Should not raise exception or send alert
        manager.check_db_size("/nonexistent/path/db.duckdb")
        mock_send.assert_not_called()

