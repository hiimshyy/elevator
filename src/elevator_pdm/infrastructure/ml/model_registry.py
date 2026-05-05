"""Model registry for tracking ONNX model versions."""
import os
from typing import Dict, Optional
from pathlib import Path


class ModelRegistry:
    """Track model versions and support hot-reload."""

    def __init__(self, models_dir: str = "models/") -> None:
        self._models_dir = models_dir
        self._models: Dict[str, str] = {}  # name → path

    def register(self, name: str, model_path: str) -> None:
        """Register a model with its file path."""
        self._models[name] = model_path

    def get_path(self, name: str) -> Optional[str]:
        """Get model file path by name."""
        return self._models.get(name)

    def list_models(self) -> Dict[str, str]:
        """List all registered models."""
        return self._models.copy()

    def model_exists(self, name: str) -> bool:
        """Check if a model file exists."""
        path = self._models.get(name)
        return path is not None and os.path.exists(path)

    def get_latest_model(self, prefix: str) -> Optional[str]:
        """Get the latest model matching a prefix.

        Returns:
            Model name, or None if not found.
        """
        matches = [name for name in self._models if name.startswith(prefix)]
        if not matches:
            return None
        # Sort by version number (assumes naming like "vibration_anomaly_v1.onnx")
        return sorted(matches)[-1]
