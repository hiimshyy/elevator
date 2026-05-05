"""ONNX Runtime adapter for model inference."""
import os
import math
from typing import Dict, Any, Optional
from pathlib import Path

from elevator_pdm.domain.interfaces.model_runtime import ModelRuntime
from elevator_pdm.domain.entities.inference_result import InferenceResult
from elevator_pdm.domain.exceptions import ModelNotLoadedError


class OnnxRuntime(ModelRuntime):
    """ONNX Runtime implementation using onnxruntime.InferenceSession."""

    def __init__(self, model_path: str) -> None:
        self._model_path = model_path
        self._session: Optional[Any] = None
        self._input_name: Optional[str] = None
        self._output_names: Optional[list[str]] = None
        # Don't load model in __init__ — let it fail lazily in predict()

    def _load_model(self) -> None:
        """Load or reload the ONNX model from disk."""
        if not os.path.exists(self._model_path):
            raise ModelNotLoadedError(f"Model file not found: {self._model_path}")

        try:
            import onnxruntime as ort
            self._session = ort.InferenceSession(self._model_path)
            # Cache input/output names
            self._input_name = self._session.get_inputs()[0].name
            self._output_names = [o.name for o in self._session.get_outputs()]
        except ImportError as e:
            raise ModelNotLoadedError(f"onnxruntime not installed: {e}") from e
        except Exception as e:
            raise ModelNotLoadedError(f"Failed to load ONNX model: {e}") from e

    def _sigmoid(self, x: float) -> float:
        """Apply sigmoid function to map value to 0-1 range."""
        return 1.0 / (1.0 + math.exp(-abs(x)))

    def _parse_isolation_forest_output(self, score: float) -> tuple[str, float, Optional[float]]:
        """Parse Isolation Forest decision_function output.

        Args:
            score: decision_function value (higher = more normal)

        Returns:
            Tuple of (status, confidence, health_score)
        """
        # Map decision_function score to status
        # Positive = inlier (normal), Negative = outlier (anomaly)
        if score > 0.1:
            status = "NORMAL"
            confidence = self._sigmoid(score * 2.0)
        elif score < -0.2:
            status = "CRITICAL"
            confidence = self._sigmoid(-score * 2.0)
        else:
            status = "WARNING"
            confidence = self._sigmoid(-abs(score) * 2.0)

        # Map score to health score (0-100)
        # Typical range: -0.3 to 0.3 for normal data
        # Map to 0-100: score=0.3 -> 100, score=-0.5 -> 0
        health_score = max(0.0, min(100.0, 50.0 + score * 100.0))

        return status, confidence, health_score

    def predict(self, features: Dict[str, float]) -> InferenceResult:
        """Run inference on a feature vector.

        Args:
            features: Dict of feature name → value

        Returns:
            InferenceResult with status, confidence, and optional health_score
        """
        if self._session is None:
            self._load_model()

        try:
            import numpy as np

            # Prepare input as numpy array
            # Assumes features are ordered consistently — use a fixed order
            feature_names = sorted(features.keys())
            input_data = np.array([[features[name] for name in feature_names]], dtype=np.float32)

            # Run inference
            outputs = self._session.run(
                self._output_names,
                {self._input_name: input_data}
            )

            # Parse outputs based on number of model outputs
            status = "NORMAL"
            confidence = 0.0
            health_score = None

            n_outputs = len(outputs)

            if n_outputs == 1:
                # Single output model (e.g., Isolation Forest decision_function)
                score_val = outputs[0]
                if isinstance(score_val, (list, np.ndarray)):
                    score_val = score_val[0]
                if isinstance(score_val, np.ndarray):
                    score_val = score_val.item()
                score = float(score_val)
                status, confidence, health_score = self._parse_isolation_forest_output(score)

            elif n_outputs == 2:
                # Isolation Forest output: [label, scores]
                # label: 1=inlier (NORMAL), -1=outlier (anomaly)
                # scores: anomaly scores (higher = more normal)
                score_val = outputs[1]  # Use scores output
                if isinstance(score_val, (list, np.ndarray)):
                    score_val = score_val[0]
                if isinstance(score_val, np.ndarray):
                    score_val = score_val.item()
                score = float(score_val)
                status, confidence, health_score = self._parse_isolation_forest_output(score)

            else:
                # Multi-output model [status, confidence, health_score?]
                if n_outputs >= 1:
                    # First output: status
                    status_val = outputs[0]
                    if isinstance(status_val, (list, np.ndarray)):
                        status_val = status_val[0]
                    if isinstance(status_val, np.ndarray):
                        status_val = status_val.item()
                    status_idx = int(status_val)
                    status_map = ["NORMAL", "WARNING", "CRITICAL", "OVERLOAD"]
                    status = status_map[status_idx] if status_idx < len(status_map) else "NORMAL"

                if n_outputs >= 2:
                    # Second output: confidence
                    conf_val = outputs[1]
                    if isinstance(conf_val, (list, np.ndarray)):
                        conf_val = conf_val[0]
                    if isinstance(conf_val, np.ndarray):
                        conf_val = conf_val.item()
                    confidence = float(conf_val)

                if n_outputs >= 3:
                    # Third output: health_score
                    health_val = outputs[2]
                    if isinstance(health_val, (list, np.ndarray)):
                        health_val = health_val[0]
                    if isinstance(health_val, np.ndarray):
                        health_val = health_val.item()
                    health_score = float(health_val)

            return InferenceResult(
                elevator_id="",  # Filled by use case
                timestamp="",  # Filled by use case
                model_name=Path(self._model_path).stem,
                model_version=self.model_version,
                status=status,
                confidence=confidence,
                health_score=health_score,
                features_json=None,  # Filled by use case
            )

        except Exception as e:
            raise ModelNotLoadedError(f"Inference failed: {e}") from e

    def reload(self) -> None:
        """Hot-reload model from disk."""
        self._load_model()

    @property
    def model_version(self) -> str:
        """Return the model file's last modified time as version."""
        if not os.path.exists(self._model_path):
            return "unknown"
        stat = os.stat(self._model_path)
        return f"modified_{int(stat.st_mtime)}"

    def get_input_names(self) -> list[str]:
        """Get expected input feature names (if model has metadata)."""
        if self._session is None:
            return []
        return [inp.name for inp in self._session.get_inputs()]
