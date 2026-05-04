"""Model runtime interface (port)."""
from abc import ABC, abstractmethod
from typing import Dict, Any

from elevator_pdm.domain.entities.inference_result import InferenceResult


class ModelRuntime(ABC):
    """Abstract interface for ML model inference.

    Infrastructure layer provides concrete implementations:
    - OnnxRuntime: ONNX Runtime CPU inference
    """

    @abstractmethod
    def predict(self, features: Dict[str, float]) -> InferenceResult:
        """Run inference on a feature vector.

        Args:
            features: Dict of feature name → value

        Returns:
            InferenceResult with status, confidence, and optional health_score
        """
        ...

    @abstractmethod
    def reload(self) -> None:
        """Hot-reload model from disk (e.g. after update)."""
        ...

    @property
    @abstractmethod
    def model_version(self) -> str:
        """Return current model version string."""
        ...
