"""MQTT Logger - Entry point."""

import sys
from pathlib import Path

from src.mqtt_logger.app import main

if __name__ == "__main__":
    config_path = sys.argv[1] if len(sys.argv) > 1 else None
    main(config_path)
