"""Pytest configuration and fixtures for Data Sleigh tests."""

import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def test_db_path(temp_dir):
    """Create a temporary database path."""
    return temp_dir / "test.duckdb"


@pytest.fixture
def test_config_path(temp_dir):
    """Create a temporary config file path."""
    return temp_dir / "test_config.toml"



