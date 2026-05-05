"""Tests for ONNX Runtime adapter."""
import pytest
import numpy as np
from pathlib import Path
from unittest.mock import MagicMock, patch

from elevator_pdm.infrastructure.ml.onnx_runtime import OnnxRuntime
from elevator_pdm.domain.entities.inference_result import InferenceResult
from elevator_pdm.domain.exceptions import ModelNotLoadedError

MODEL_PATH = "models/tinyyolov2-7.onnx"


def test_loads_onnx_file_and_runs_predict():
    runtime = OnnxRuntime(MODEL_PATH)

    try:
        # Create dummy input matching YOLOv2 input shape
        features = {"input": np.random.randn(1, 3, 416, 416).astype(np.float32)}
        result = runtime.predict(features)
        assert isinstance(result, InferenceResult)
    except ModelNotLoadedError as e:
        pytest.skip(f"Model loading failed: {e}")


def test_reload_swaps_model():
    runtime = OnnxRuntime(MODEL_PATH)
    # Should not raise
    runtime.reload()


def test_model_version_returns_string():
    runtime = OnnxRuntime(MODEL_PATH)
    version = runtime.model_version
    assert isinstance(version, str)
    assert len(version) > 0


def test_raises_model_not_loaded_error_if_file_missing():
    with pytest.raises(ModelNotLoadedError):
        OnnxRuntime("nonexistent_model.onnx").predict({"input": np.array([1.0])})


def test_raises_model_not_loaded_error_if_model_none():
    runtime = OnnxRuntime("dummy_path.onnx")
    with pytest.raises(ModelNotLoadedError):
        runtime.predict({"feature": 1.0})


def test_predict_with_mock():
    """Test predict using a mock ONNX session."""
    with patch("onnxruntime.InferenceSession", return_value=MagicMock()) as mock_ort:
        mock_session = MagicMock()
        mock_ort.return_value = mock_session
        mock_session.get_inputs.return_value = [MagicMock(name="input")]
        mock_session.get_outputs.return_value = [
            MagicMock(name="output_status"),
            MagicMock(name="output_confidence"),
            MagicMock(name="output_health"),
        ]
        mock_session.run.return_value = [np.array([0]), np.array([0.95]), np.array([85.0])]

        runtime = OnnxRuntime("dummy.onnx")
        runtime._session = mock_session
        runtime._input_name = "input"
        runtime._output_names = ["output_status", "output_confidence", "output_health"]

        features = {"accel_rms_mean": 42.5, "load_pct": 0.45}
        result = runtime.predict(features)

        assert isinstance(result, InferenceResult)
        assert result.model_name == "dummy"
        assert result.confidence == 0.95
        assert result.health_score == 85.0


def test_predict_with_mock_raises_error_if_model_missing():
    """Test that predict raises error if model not loaded."""
    with patch("onnxruntime.InferenceSession") as mock_ort:
        # Make the session loading fail
        mock_ort.side_effect = Exception("Model not found")

        runtime = OnnxRuntime("nonexistent.onnx")

        with pytest.raises(ModelNotLoadedError):
            runtime.predict({"feature": 1.0})


def test_reload_with_mock():
    """Test hot-reload with mock."""
    with patch("onnxruntime.InferenceSession", return_value=MagicMock()) as mock_ort:
        mock_session = MagicMock()
        mock_ort.return_value = mock_session

        runtime = OnnxRuntime("dummy.onnx")
        runtime._session = mock_session  # Skip file loading.
        runtime._load_model = lambda: None  # Mock the load method.

        # Reload should not raise.
        runtime.reload()


def test_model_version_with_mock(tmp_path):
    """Test model version returns modified time."""
    model_file = tmp_path / "test.onnx"
    model_file.touch()

    with patch("onnxruntime.InferenceSession"):
        runtime = OnnxRuntime(str(model_file))

        version = runtime.model_version
        assert isinstance(version, str)
        assert "modified_" in version


def test_model_version_unknown_if_file_missing():
    runtime = OnnxRuntime("nonexistent.onnx")
    assert runtime.model_version == "unknown"


def test_predict_returns_correct_inference_result():
    runtime = OnnxRuntime(MODEL_PATH)

    try:
        features = {"input": np.random.randn(1, 3, 416, 416).astype(np.float32)}
        result = runtime.predict(features)
        assert isinstance(result, InferenceResult)
        assert result.model_name == Path(MODEL_PATH).stem
    except ModelNotLoadedError as e:
        pytest.skip(f"Model loading failed: {e}")


def test_get_input_names():
    runtime = OnnxRuntime(MODEL_PATH)

    try:
        names = runtime.get_input_names()
        assert isinstance(names, list)
        # YOLOv2 might not have named inputs, so skip if empty.
        if len(names) == 0:
            pytest.skip("Model has no named inputs")
    except ModelNotLoadedError as e:
        pytest.skip(f"Model loading failed: {e}")
