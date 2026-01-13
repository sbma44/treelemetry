"""Tests for season-aware behavior."""

from datetime import date, datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from data_sleigh.config import Config, SeasonConfig


def test_is_in_season_true():
    """Test season check when date is within season."""
    # Create a mock app with season config
    with patch("data_sleigh.app.DataSleighApp.__init__", return_value=None):
        from data_sleigh.app import DataSleighApp

        app = DataSleighApp.__new__(DataSleighApp)
        app.config = Mock()

        # Set season to include today
        today = date.today()
        app.config.season = SeasonConfig(
            start=date(today.year, today.month, 1),
            end=date(today.year, today.month, 28),
        )

        assert app.is_in_season() is True


def test_is_in_season_false():
    """Test season check when date is outside season."""
    with patch("data_sleigh.app.DataSleighApp.__init__", return_value=None):
        from data_sleigh.app import DataSleighApp

        app = DataSleighApp.__new__(DataSleighApp)
        app.config = Mock()

        # Set season to past dates
        app.config.season = SeasonConfig(
            start=date(2020, 1, 1),
            end=date(2020, 1, 31),
        )

        assert app.is_in_season() is False


def test_is_in_season_boundary_start():
    """Test season check on start date."""
    with patch("data_sleigh.app.DataSleighApp.__init__", return_value=None):
        from data_sleigh.app import DataSleighApp

        app = DataSleighApp.__new__(DataSleighApp)
        app.config = Mock()

        # Set season to start today
        today = date.today()
        app.config.season = SeasonConfig(
            start=today,
            end=date(today.year, 12, 31),
        )

        assert app.is_in_season() is True


def test_is_in_season_boundary_end():
    """Test season check on end date."""
    with patch("data_sleigh.app.DataSleighApp.__init__", return_value=None):
        from data_sleigh.app import DataSleighApp

        app = DataSleighApp.__new__(DataSleighApp)
        app.config = Mock()

        # Set season to end today
        today = date.today()
        app.config.season = SeasonConfig(
            start=date(today.year, 1, 1),
            end=today,
        )

        assert app.is_in_season() is True



