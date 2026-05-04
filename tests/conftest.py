"""Shared test fixtures."""
import pytest


@pytest.fixture
def sample_elevator_id() -> str:
    """Return a test elevator ID."""
    return "elev-test-001"


@pytest.fixture
def sample_vibration_reading() -> dict:
    """Return a sample vibration sensor reading."""
    return {
        "sensor_id": "ES-VS-01",
        "accel_rms_mg": 42.3,
        "velocity_rms_mms": 1.85,
        "peak_accel_mg": 98.7,
        "temperature_c": 38.2,
        "timestamp": "2025-06-15T10:30:00Z",
    }


@pytest.fixture
def sample_temp_humidity_reading() -> dict:
    """Return a sample temperature/humidity sensor reading."""
    return {
        "sensor_id": "ES35-SW",
        "temperature_c": 28.5,
        "humidity_pct": 62.3,
        "timestamp": "2025-06-15T10:30:00Z",
    }


@pytest.fixture
def sample_load_reading() -> dict:
    """Return a sample load cell reading."""
    return {
        "sensor_id": "RW-ST01D",
        "load_kg": 320.0,
        "timestamp": "2025-06-15T10:30:00Z",
    }
