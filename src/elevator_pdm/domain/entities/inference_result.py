"""Inference result domain entity."""
from dataclasses import dataclass


@dataclass
class InferenceResult:
    """Result of running an ML model on a sensor feature vector."""

    elevator_id: str
    timestamp: str
    model_name: str  # vibration_anomaly | health_score | overload
    model_version: str  # e.g. 1.2.0
    status: str  # NORMAL | WARNING | CRITICAL | OVERLOAD
    confidence: float = 0.0
    health_score: float | None = None
    features_json: str | None = None
    id: int | None = None
