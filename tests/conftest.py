"""Pytest fixtures for OBD toolkit tests."""

import pytest
from unittest.mock import MagicMock


@pytest.fixture
def mock_obd_connection():
    """Create a mock OBD connection for testing."""
    mock = MagicMock()
    mock.is_connected.return_value = True
    mock.status.return_value = "Car Connected"
    return mock


@pytest.fixture
def sample_dtc_codes():
    """Sample DTC codes for testing."""
    return [
        {"code": "P0300", "description": "Random/Multiple Cylinder Misfire Detected"},
        {"code": "P0420", "description": "Catalyst System Efficiency Below Threshold (Bank 1)"},
    ]


@pytest.fixture
def sample_vin():
    """Sample VIN for testing."""
    return "1HGBH41JXMN109186"
