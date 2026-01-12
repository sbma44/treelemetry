"""Tests for backup functionality."""

from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from data_sleigh.backup import BackupManager
from data_sleigh.config import BackupConfig, S3Config
from data_sleigh.storage import MessageStore


@pytest.fixture
def backup_config():
    """Create a test backup configuration."""
    return BackupConfig(day_of_month=1, hour=3)


@pytest.fixture
def s3_config():
    """Create a test S3 configuration."""
    return S3Config(
        bucket="test-bucket",
        json_key="test.json",
        backup_prefix="backups/",
        aws_access_key_id="test-key",
        aws_secret_access_key="test-secret",
    )


def test_should_backup_correct_time(backup_config, s3_config):
    """Test that backup triggers at correct day and hour."""
    with patch("data_sleigh.backup.boto3.client"):
        manager = BackupManager(backup_config, s3_config)

        # Mock datetime to be on backup day/hour
        with patch("data_sleigh.backup.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 1, 1, 3, 0)  # Day 1, Hour 3
            assert manager.should_backup() is True


def test_should_backup_wrong_day(backup_config, s3_config):
    """Test that backup doesn't trigger on wrong day."""
    with patch("data_sleigh.backup.boto3.client"):
        manager = BackupManager(backup_config, s3_config)

        # Mock datetime to be on wrong day
        with patch("data_sleigh.backup.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 1, 15, 3, 0)  # Day 15, Hour 3
            assert manager.should_backup() is False


def test_should_backup_wrong_hour(backup_config, s3_config):
    """Test that backup doesn't trigger on wrong hour."""
    with patch("data_sleigh.backup.boto3.client"):
        manager = BackupManager(backup_config, s3_config)

        # Mock datetime to be on wrong hour
        with patch("data_sleigh.backup.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 1, 1, 10, 0)  # Day 1, Hour 10
            assert manager.should_backup() is False


def test_should_backup_once_per_month(backup_config, s3_config):
    """Test that backup only triggers once per month."""
    with patch("data_sleigh.backup.boto3.client"):
        manager = BackupManager(backup_config, s3_config)

        # First call on correct day/hour should return True
        with patch("data_sleigh.backup.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 1, 1, 3, 0)
            assert manager.should_backup() is True

            # Record that backup happened
            manager.last_backup_month = (2025, 1)

            # Second call same month should return False
            assert manager.should_backup() is False

        # Next month should return True again
        with patch("data_sleigh.backup.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 2, 1, 3, 0)
            assert manager.should_backup() is True


def test_backup_database_creates_archive(backup_config, s3_config, test_db_path):
    """Test that backup creates local archive."""
    # Create a test database
    store = MessageStore(test_db_path, batch_size=1)
    store.create_table("test")
    store.insert_message("test", "test/topic", b"test", qos=1, retain=False)
    store.close()

    assert test_db_path.exists()

    # Create backup manager with mocked S3 client
    with patch("data_sleigh.backup.boto3.client") as mock_boto3:
        mock_s3_client = Mock()
        mock_boto3.return_value = mock_s3_client

        manager = BackupManager(backup_config, s3_config)

        # Create a fresh store instance for backup
        store = MessageStore(test_db_path, batch_size=1)

        # Perform backup
        with patch("data_sleigh.backup.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 1, 1, 3, 0)
            manager.backup_database(test_db_path, store)

        # Check that S3 upload was called
        assert mock_s3_client.upload_file.called

        # Check that archive was created
        archive_dir = test_db_path.parent / "archive"
        assert archive_dir.exists()

        # Check that original DB was moved
        assert not test_db_path.exists()


