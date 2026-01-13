"""Tests for configuration management."""

from datetime import date
from pathlib import Path

import pytest

from data_sleigh.config import load_config


def test_load_config_with_all_sections(test_config_path):
    """Test loading a complete configuration file."""
    config_content = """
[mqtt]
broker = "localhost"
port = 1883

[database]
path = "/app/data/test.db"
batch_size = 100
flush_interval = 60

[[topics]]
pattern = "test/#"
table_name = "test_table"

[logging]
level = "INFO"

[alerting]
email_to = "test@example.com"

[yolink]
enabled = false

[season]
start = "2024-12-01"
end = "2025-01-15"

[s3]
bucket = "test-bucket"
json_key = "test.json"
backup_prefix = "backups/"

[upload]
interval_seconds = 30

[backup]
day_of_month = 1
hour = 3
"""
    test_config_path.write_text(config_content)

    config = load_config(test_config_path)

    assert config.mqtt.broker == "localhost"
    assert config.mqtt.port == 1883
    assert config.database.path == "/app/data/test.db"
    assert len(config.topics) == 1
    assert config.topics[0].pattern == "test/#"
    assert config.season.start == date(2024, 12, 1)
    assert config.season.end == date(2025, 1, 15)
    assert config.s3.bucket == "test-bucket"
    assert config.upload.interval_seconds == 30
    assert config.backup.day_of_month == 1


def test_load_config_missing_required_section(test_config_path):
    """Test that missing required sections raise ValueError."""
    config_content = """
[mqtt]
broker = "localhost"

# Missing database section
"""
    test_config_path.write_text(config_content)

    with pytest.raises(ValueError, match="Missing required section: database"):
        load_config(test_config_path)


def test_config_file_not_found():
    """Test that missing config file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        load_config("nonexistent.toml")



