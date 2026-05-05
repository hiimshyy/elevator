"""Pydantic response schemas for API."""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class HealthCheckResponse(BaseModel):
    """Response schema for health check."""

    db: str
    sensors: str
    models: str


class SensorReadingResponse(BaseModel):
    """Response schema for sensor reading."""

    id: Optional[int] = None
    elevator_id: str
    timestamp: datetime
    accel_rms_mg: float
    velocity_rms_mms: Optional[float] = None
    peak_accel_mg: Optional[float] = None
    vib_temperature_c: Optional[float] = None
    env_temperature_c: Optional[float] = None
    env_humidity_pct: Optional[float] = None
    load_kg: Optional[float] = None
    synced: int = 0


class InferenceResponse(BaseModel):
    """Response schema for inference result."""

    id: Optional[int] = None
    elevator_id: str
    timestamp: datetime
    model_name: str
    model_version: str
    status: str  # NORMAL | WARNING | CRITICAL | OVERLOAD
    confidence: float
    health_score: Optional[float] = None
    features_json: Optional[str] = None


class PredictResponse(BaseModel):
    """Response schema for prediction endpoint."""

    elevator_id: str
    status: str
    confidence: float
    health_score: Optional[float] = None
    features: Optional[dict] = None
    alert_triggered: bool = False
    model_version: str
    inference_ms: float


class ElevatorResponse(BaseModel):
    """Response schema for elevator."""

    id: str
    max_capacity_kg: int
    created_at: datetime
    latest_health_score: Optional[float] = None
    status: Optional[str] = None


class AlertResponse(BaseModel):
    """Response schema for alert."""

    id: Optional[int] = None
    elevator_id: str
    timestamp: datetime
    severity: str
    message: str
    acknowledged: int = 0
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None


class MaintenanceResponse(BaseModel):
    """Response schema for maintenance schedule."""

    id: Optional[int] = None
    elevator_id: str
    recommended_date: str
    urgency: str
    reason: str
    estimated_rul_hours: Optional[float] = None
    status: str = "pending"
    completed_at: Optional[str] = None
    technician: Optional[str] = None
    created_at: datetime


class ModelReloadResponse(BaseModel):
    """Response schema for model reload."""

    status: str
    model: str
    version: str
