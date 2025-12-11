"""Static data resources for OBD toolkit."""

import json
from pathlib import Path

DATA_DIR = Path(__file__).parent


def load_dtc_codes() -> dict:
    """Load DTC codes database."""
    with open(DATA_DIR / "dtc_codes.json", "r") as f:
        return json.load(f)


def load_manufacturers() -> dict:
    """Load manufacturer WMI codes."""
    with open(DATA_DIR / "manufacturers.json", "r") as f:
        return json.load(f)
