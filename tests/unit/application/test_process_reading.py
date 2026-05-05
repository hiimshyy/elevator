"""Tests for ProcessReadingUseCase."""
import pytest
from unittest.mock import MagicMock, patch

from elevator_pdm.application.use_cases.process_reading import ProcessReadingUseCase
from elevator_pdm.application.services.feature_engineer import FeatureEngineer


@pytest.fixture
def use_case():
    """Create a ProcessReadingUseCase with mock queue and real feature engineer."""
    queue = MagicMock()
    feature_engineer = FeatureEngineer(max_capacity_kg=1000)
    return ProcessReadingUseCase(queue, feature_engineer), queue, feature_engineer


def test_dequeues_from_redis(use_case):
    uc, queue, fe = use_case

    queue.dequeue.return_value = {
        "elevator_id": "test-001",
        "sensor_id": "ES-VS-01",
        "accel_rms_mg": 42.5,
        "velocity_rms_mms": 12.3,
        "timestamp": "2025-01-01T00:00:00+00:00",
    }

    result = uc.execute()

    queue.dequeue.assert_called_once_with(timeout=5)
    assert result is not None
    assert "accel_rms_mean" in result


def test_passes_reading_to_feature_engineer(use_case):
    uc, queue, fe = use_case

    reading = {
        "accel_rms_mg": 42.5,
        "velocity_rms_mms": 12.3,
        "peak_accel_mg": 98.0,
        "vib_temperature_c": 25.0,
        "env_temperature_c": 23.0,
        "env_humidity_pct": 60.0,
        "load_kg": 450.0,
    }
    queue.dequeue.return_value = reading

    result = uc.execute()

    assert result is not None
    # Should have all 11 features
    assert len(result) == 11


def test_returns_feature_dict_ready_for_model(use_case):
    uc, queue, fe = use_case

    reading = {
        "accel_rms_mg": 42.5,
        "velocity_rms_mms": 12.3,
        "peak_accel_mg": 98.0,
        "vib_temperature_c": 25.0,
        "env_temperature_c": 23.0,
        "env_humidity_pct": 60.0,
        "load_kg": 450.0,
    }
    queue.dequeue.return_value = reading

    result = uc.execute()

    # All features present
    expected_features = [
        "accel_rms_mean", "accel_rms_std", "accel_delta", "accel_roc",
        "velocity_rms_z", "peak_to_rms_ratio", "motor_temp_delta",
        "humidity_trend", "load_pct", "load_variance", "multivariate_score"
    ]
    for feat in expected_features:
        assert feat in result, f"Missing feature: {feat}"


def test_handles_empty_queue_gracefully(use_case):
    uc, queue, fe = use_case

    # Queue returns None (empty/timeout)
    queue.dequeue.return_value = None

    result = uc.execute()

    assert result is None


def test_handles_empty_queue_with_none(use_case):
    uc, queue, fe = use_case

    queue.dequeue.return_value = None

    result = uc.execute()

    assert result is None


def test_execute_batch_processes_multiple_readings(use_case):
    uc, queue, fe = use_case

    # Return 3 readings then None
    readings = [
        {"accel_rms_mg": 42.5},
        {"accel_rms_mg": 50.0},
        {"accel_rms_mg": 55.0},
    ]
    queue.dequeue.side_effect = readings + [None]

    results = uc.execute_batch(max_readings=10, timeout=1)

    assert len(results) == 3
    assert all(len(r) == 11 for r in results)


def test_execute_batch_stops_at_max(use_case):
    uc, queue, fe = use_case

    # Return 5 readings
    readings = [{"accel_rms_mg": float(i * 10)} for i in range(5)]
    queue.dequeue.side_effect = readings + [None]

    results = uc.execute_batch(max_readings=3, timeout=1)

    assert len(results) == 3


def test_execute_batch_with_empty_queue(use_case):
    uc, queue, fe = use_case

    queue.dequeue.return_value = None

    results = uc.execute_batch(max_readings=10)

    assert len(results) == 0


def test_returns_none_when_queue_empty(use_case):
    uc, queue, fe = use_case

    queue.dequeue.return_value = None

    result = uc.execute()

    assert result is None


def test_get_last_features_returns_none_initially(use_case):
    uc, queue, fe = use_case

    result = uc.get_last_features()

    assert result is None


def test_get_last_features_returns_after_processing(use_case):
    uc, queue, fe = use_case

    reading = {"accel_rms_mg": 42.5, "load_kg": 450.0}
    queue.dequeue.return_value = reading

    uc.execute()

    last = uc.get_last_features()
    assert last is not None
    assert "accel_rms_mean" in last


def test_uses_correct_timeout(use_case):
    uc, queue, fe = use_case

    queue.dequeue.return_value = None

    uc.execute(timeout=10)

    queue.dequeue.assert_called_once_with(timeout=10)


def test_preserves_feature_engineer_state(use_case):
    """Test that feature engineer's rolling windows are updated."""
    uc, queue, fe = use_case

    # Process multiple readings
    for i in range(5):
        queue.dequeue.return_value = {"accel_rms_mg": float(i * 10)}
        result = uc.execute()
        assert result is not None

    # The feature engineer should have a populated window
    assert len(fe._accel_window) == 5
