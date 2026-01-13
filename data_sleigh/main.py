"""Data Sleigh - Entry point."""

import sys
from pathlib import Path

from src.data_sleigh.app import main

if __name__ == "__main__":
    config_path = sys.argv[1] if len(sys.argv) > 1 else None
    main(config_path)



