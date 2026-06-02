"""Tests for PollSensorsUseCase."""

from unittest.mock import MagicMock

import pytest

from elevator_pdm.application.use_cases.poll_sensors import PollSensorsUseCase
from elevator_pdm.domain.entities.sensor_reading import SensorReading
from elevator_pdm.domain.exceptions import SensorUnavailableError


@pytest.fixture
def mocks():
    """Create mock gateway, repo, and queue."""
    gateway = MagicMock()
    repo = MagicMock()
    queue = MagicMock()
    mqtt_publisher = MagicMock()
    mqtt_publisher.publish_reading.return_value = True
    use_case = PollSensorsUseCase(gateway, repo, queue, mqtt_publisher=mqtt_publisher)
    return gateway, repo, queue, mqtt_publisher, use_case


def test_calls_all_three_sensor_methods(mocks):
    gateway, repo, queue, mqtt_publisher, use_case = mocks

    # Setup successful returns
    gateway.read_vibration.return_value = {
        "sensor_id": "ES-VS-01", "accel_rms_mg": 42.5, "timestamp": "2025-01-01T00:00:00+00:00"
    }
    gateway.read_temp_humidity.return_value = {
        "sensor_id": "ES35-SW", "temperature_c": 25.0, "timestamp": "2025-01-01T00:00:00+00:00"
    }
    gateway.read_load.return_value = {
        "sensor_id": "RW-ST01D", "load_kg": 450.0, "timestamp": "2025-01-01T00:00:00+00:00"
    }

    result = use_case.execute("test-elev-001")

    assert gateway.read_vibration.called
    assert gateway.read_temp_humidity.called
    assert gateway.read_load.called
    assert len(result["success"]) == 3
    assert len(result["failed"]) == 0


def test_persists_readings_to_repository(mocks):
    gateway, repo, queue, mqtt_publisher, use_case = mocks

    gateway.read_vibration.return_value = {
        "sensor_id": "ES-VS-01", "accel_rms_mg": 42.5, "timestamp": "2025-01-01T00:00:00+00:00"
    }
    gateway.read_temp_humidity.return_value = {
        "sensor_id": "ES35-SW", "temperature_c": 25.0, "timestamp": "2025-01-01T00:00:00+00:00"
    }
    gateway.read_load.return_value = {
        "sensor_id": "RW-ST01D", "load_kg": 450.0, "timestamp": "2025-01-01T00:00:00+00:00"
    }

    use_case.execute("test-elev-001")

    # Should save 3 readings
    assert repo.save.call_count == 3


def test_enqueues_readings_to_redis(mocks):
    gateway, repo, queue, mqtt_publisher, use_case = mocks

    gateway.read_vibration.return_value = {
        "sensor_id": "ES-VS-01", "accel_rms_mg": 42.5, "timestamp": "2025-01-01T00:00:00+00:00"
    }
    gateway.read_temp_humidity.return_value = {
        "sensor_id": "ES35-SW", "temperature_c": 25.0, "timestamp": "2025-01-01T00:00:00+00:00"
    }
    gateway.read_load.return_value = {
        "sensor_id": "RW-ST01D", "load_kg": 450.0, "timestamp": "2025-01-01T00:00:00+00:00"
    }

    use_case.execute("test-elev-001")

    # Should enqueue 3 readings
    assert queue.enqueue.call_count == 3


def test_publishes_readings_to_mqtt(mocks):
    gateway, repo, queue, mqtt_publisher, use_case = mocks

    gateway.read_vibration.return_value = {
        "sensor_id": "ES-VS-01", "accel_rms_mg": 42.5, "timestamp": "2025-01-01T00:00:00+00:00"
    }
    gateway.read_temp_humidity.return_value = {
        "sensor_id": "ES35-SW", "temperature_c": 25.0, "timestamp": "2025-01-01T00:00:00+00:00"
    }
    gateway.read_load.return_value = {
        "sensor_id": "RW-ST01D", "load_kg": 450.0, "timestamp": "2025-01-01T00:00:00+00:00"
    }

    use_case.execute("test-elev-001")

    assert mqtt_publisher.publish_reading.call_count == 3


def test_single_sensor_failure_does_not_block_others(mocks):
    gateway, repo, queue, mqtt_publisher, use_case = mocks

    # Only vibration fails
    gateway.read_vibration.side_effect = SensorUnavailableError("Vibration sensor unavailable")
    gateway.read_temp_humidity.return_value = {
        "sensor_id": "ES35-SW", "temperature_c": 25.0, "timestamp": "2025-01-01T00:00:00+00:00"
    }
    gateway.read_load.return_value = {
        "sensor_id": "RW-ST01D", "load_kg": 450.0, "timestamp": "2025-01-01T00:00:00+00:00"
    }

    result = use_case.execute("test-elev-001")

    # Temp and load should succeed
    assert "ES35-SW" in result["success"]
    assert "RW-ST01D" in result["success"]
    assert "vibration" in result["failed"]
    assert len(result["success"]) == 2
    assert len(result["failed"]) == 1


def test_backoff_doubles_on_consecutive_errors(mocks):
    gateway, repo, queue, mqtt_publisher, use_case = mocks

    # Make vibration sensor always fail
    gateway.read_vibration.side_effect = SensorUnavailableError("Timeout")

    # First failure
    use_case.execute("test-elev-001")
    assert use_case._consecutive_errors["vibration"] == 1
    assert use_case._backoff_delay("vibration") == 1.0  # 2**(1-1) = 1

    # Second failure
    use_case.execute("test-elev-001")
    assert use_case._consecutive_errors["vibration"] == 2
    assert use_case._backoff_delay("vibration") == 2.0  # 2**(2-1) = 2

    # Third failure
    use_case.execute("test-elev-001")
    assert use_case._consecutive_errors["vibration"] == 3
    assert use_case._backoff_delay("vibration") == 4.0  # 2**(3-1) = 4


def test_backoff_caps_at_max_60s(mocks):
    gateway, repo, queue, mqtt_publisher, use_case = mocks

    # Make vibration sensor always fail
    gateway.read_vibration.side_effect = SensorUnavailableError("Timeout")

    # Simulate many consecutive errors
    for i in range(10):
        use_case.execute("test-elev-001")

    assert use_case._consecutive_errors["vibration"] == 10
    # 2**9 = 512, but capped at 60
    assert use_case._backoff_delay("vibration") == 60.0


def test_backoff_resets_on_success(mocks):
    gateway, repo, queue, mqtt_publisher, use_case = mocks

    # First, make it fail
    gateway.read_vibration.side_effect = SensorUnavailableError("Timeout")
    use_case.execute("test-elev-001")
    assert use_case._consecutive_errors["vibration"] == 1

    # Now make it succeed
    gateway.read_vibration.side_effect = None
    gateway.read_vibration.return_value = {
        "sensor_id": "ES-VS-01", "accel_rms_mg": 42.5, "timestamp": "2025-01-01T00:00:00+00:00"
    }
    use_case.execute("test-elev-001")

    # Should reset to 0
    assert use_case._consecutive_errors["vibration"] == 0
    assert use_case._backoff_delay("vibration") == 0.0


def test_builds_correct_sensor_reading_entity(mocks):
    gateway, repo, queue, mqtt_publisher, use_case = mocks

    gateway.read_vibration.return_value = {
        "sensor_id": "ES-VS-01",
        "accel_rms_mg": 42.5,
        "velocity_rms_mms": 12.3,
        "peak_accel_mg": 98.0,
        "temperature_c": 25.0,
        "timestamp": "2025-01-01T00:00:00+00:00"
    }
    gateway.read_temp_humidity.return_value = {
        "sensor_id": "ES35-SW",
        "temperature_c": 25.0,
        "humidity_pct": 60.0,
        "timestamp": "2025-01-01T00:00:00+00:00"
    }
    gateway.read_load.return_value = {
        "sensor_id": "RW-ST01D",
        "load_kg": 450.0,
        "timestamp": "2025-01-01T00:00:00+00:00"
    }

    use_case.execute("test-elev-001")

    # Check that repo.save was called with correct SensorReading entities
    calls = repo.save.call_args_list
    assert len(calls) == 3

    # Verify the vibration reading
    vib_reading = calls[0][0][0]  # First call, first arg
    assert isinstance(vib_reading, SensorReading)
    assert vib_reading.sensor_id == "ES-VS-01"
    assert vib_reading.accel_rms_mg == 42.5


def test_get_backoff_status(mocks):
    gateway, repo, queue, mqtt_publisher, use_case = mocks

    # Simulate some errors
    gateway.read_vibration.side_effect = SensorUnavailableError("Timeout")
    use_case.execute("test-elev-001")

    status = use_case.get_backoff_status()
    assert "vibration" in status
    assert status["vibration"]["consecutive_errors"] == 1
    assert status["vibration"]["current_backoff_s"] == 1.0
