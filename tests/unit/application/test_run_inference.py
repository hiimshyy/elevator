"""Tests for RunInferenceUseCase."""
import pytest
from unittest.mock import MagicMock, patch

from elevator_pdm.application.use_cases.run_inference import RunInferenceUseCase
from elevator_pdm.domain.entities.inference_result import InferenceResult
from elevator_pdm.domain.exceptions import ModelNotLoadedError


@pytest.fixture
def use_case():
    """Create RunInferenceUseCase with mock dependencies."""
    runtime = MagicMock()
    repo = MagicMock()
    event_bus = MagicMock()
    return RunInferenceUseCase(runtime, repo, event_bus), runtime, repo, event_bus


def test_calls_model_runtime_with_correct_features(use_case):
    uc, runtime, repo, bus = use_case

    # Setup runtime to return a result
    runtime.predict.return_value = InferenceResult(
        elevator_id="",
        timestamp="",
        model_name="vibration_anomaly",
        model_version="1.0",
        status="WARNING",
        confidence=0.85,
    )

    features = {"accel_rms_mean": 42.5, "load_pct": 0.45}
    uc.execute("test-elev-001", features)

    # Verify predict was called with correct features
    runtime.predict.assert_called_once_with(features)


def test_persists_result_to_inference_repo(use_case):
    uc, runtime, repo, bus = use_case

    runtime.predict.return_value = InferenceResult(
        elevator_id="",
        timestamp="",
        model_name="vibration_anomaly",
        model_version="1.0",
        status="WARNING",
        confidence=0.85,
    )

    features = {"accel_rms_mean": 42.5}
    uc.execute("test-elev-001", features)

    # Verify save was called
    repo.save.assert_called_once()
    saved_result = repo.save.call_args[0][0]
    assert saved_result.elevator_id == "test-elev-001"
    assert saved_result.status == "WARNING"


def test_publishes_anomaly_event_for_warning(use_case):
    uc, runtime, repo, bus = use_case

    runtime.predict.return_value = InferenceResult(
        elevator_id="",
        timestamp="",
        model_name="vibration_anomaly",
        model_version="1.0",
        status="WARNING",
        confidence=0.85,
    )

    features = {"accel_rms_mean": 42.5}
    uc.execute("test-elev-001", features)

    # Verify event was published
    bus.publish.assert_called_once_with(
        "anomaly_detected",
        {
            "elevator_id": "test-elev-001",
            "status": "WARNING",
            "confidence": 0.85,
            "health_score": None,
            "model_name": "vibration_anomaly",
        }
    )


def test_publishes_anomaly_event_for_critical(use_case):
    uc, runtime, repo, bus = use_case

    runtime.predict.return_value = InferenceResult(
        elevator_id="",
        timestamp="",
        model_name="vibration_anomaly",
        model_version="1.0",
        status="CRITICAL",
        confidence=0.95,
    )

    features = {"accel_rms_mean": 150.0}
    uc.execute("test-elev-001", features)

    # Verify event was published
    bus.publish.assert_called_once()
    assert bus.publish.call_args[0][1]["status"] == "CRITICAL"


def test_does_not_publish_event_for_normal(use_case):
    uc, runtime, repo, bus = use_case

    runtime.predict.return_value = InferenceResult(
        elevator_id="",
        timestamp="",
        model_name="vibration_anomaly",
        model_version="1.0",
        status="NORMAL",
        confidence=0.95,
    )

    features = {"accel_rms_mean": 42.5}
    uc.execute("test-elev-001", features)

    # Verify NO event was published
    bus.publish.assert_not_called()


def test_returns_inference_result(use_case):
    uc, runtime, repo, bus = use_case

    runtime.predict.return_value = InferenceResult(
        elevator_id="",
        timestamp="",
        model_name="vibration_anomaly",
        model_version="1.0",
        status="WARNING",
        confidence=0.85,
        health_score=45.0,
    )

    features = {"accel_rms_mean": 42.5}
    result = uc.execute("test-elev-001", features)

    assert isinstance(result, InferenceResult)
    assert result.elevator_id == "test-elev-001"
    assert result.status == "WARNING"
    assert result.confidence == 0.85
    assert result.health_score == 45.0


def test_sets_model_version_from_runtime(use_case):
    uc, runtime, repo, bus = use_case

    runtime.model_version = "v2.0"
    runtime.predict.return_value = InferenceResult(
        elevator_id="",
        timestamp="",
        model_name="vibration_anomaly",
        model_version="1.0",  # Will be overwritten
        status="WARNING",
        confidence=0.85,
    )

    features = {"accel_rms_mean": 42.5}
    result = uc.execute("test-elev-001", features)

    assert result.model_version == "v2.0"


def test_sets_features_json(use_case):
    uc, runtime, repo, bus = use_case

    runtime.predict.return_value = InferenceResult(
        elevator_id="",
        timestamp="",
        model_name="vibration_anomaly",
        model_version="1.0",
        status="WARNING",
        confidence=0.85,
    )

    features = {"accel_rms_mean": 42.5, "load_pct": 0.45}
    result = uc.execute("test-elev-001", features)

    # Features should be serialized to JSON string
    assert "accel_rms_mean" in result.features_json
    assert "load_pct" in result.features_json


def test_raises_error_if_model_not_loaded(use_case):
    uc, runtime, repo, bus = use_case

    runtime.predict.side_effect = ModelNotLoadedError("Model not loaded")

    features = {"accel_rms_mean": 42.5}

    with pytest.raises(ModelNotLoadedError):
        uc.execute("test-elev-001", features)


def test_works_without_event_bus():
    """Test that use case works when event_bus is None."""
    runtime = MagicMock()
    repo = MagicMock()

    uc = RunInferenceUseCase(runtime, repo, event_bus=None)

    runtime.predict.return_value = InferenceResult(
        elevator_id="",
        timestamp="",
        model_name="vibration_anomaly",
        model_version="1.0",
        status="CRITICAL",
        confidence=0.95,
    )

    features = {"accel_rms_mean": 150.0}
    result = uc.execute("test-elev-001", features)

    # Should not raise
    assert result.status == "CRITICAL"
    # Repo should still save
    repo.save.assert_called_once()
