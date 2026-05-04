"""Inference result domain entity."""
from dataclasses import dataclass
from typing import Optional


@dataclass
class InferenceResult:
    """Result of running an ML model on sensor feature vector."""

    elevator_id: str
    timestamp: str
    model_name: str  # vibration_anomaly | health_score | overload
    model_version: str  # e.g. '1.2.0'
    status: str  # NORMAL | WARNING | CRITICAL | OVERLOAD
    confidence: float = 0.0  # 0.0–1.0
    health_score: Optional[float] = None  # 0–100
    features_json: Optional[str] = None  # JSON snapshot for audit
