"""Pydantic response schemas for API."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from elevator_pdm.domain.entities.controller_snapshot import ControllerSnapshot


class HealthCheckResponse(BaseModel):
    """Response schema for health check."""

    db: str
    sensors: str
    models: str


class SensorReadingResponse(BaseModel):
    """Response schema for sensor reading."""

    id: int | None = None
    elevator_id: str
    timestamp: datetime
    accel_rms_mg: float | None = None
    velocity_rms_mms: float | None = None
    peak_accel_mg: float | None = None
    vib_temperature_c: float | None = None
    env_temperature_c: float | None = None
    env_humidity_pct: float | None = None
    load_kg: float | None = None
    controller_register_1047: int | None = None
    controller_register_0x2121: int | None = None
    controller_register_0x2122: int | None = None
    synced: int = 0


class InferenceResponse(BaseModel):
    """Response schema for inference result."""

    id: int | None = None
    elevator_id: str
    timestamp: datetime
    model_name: str
    model_version: str
    status: str  # NORMAL | WARNING | CRITICAL | OVERLOAD
    confidence: float
    health_score: float | None = None
    features_json: str | None = None


class PredictResponse(BaseModel):
    """Response schema for prediction endpoint."""

    elevator_id: str
    status: str
    confidence: float
    health_score: float | None = None
    features: dict | None = None
    alert_triggered: bool = False
    model_version: str
    inference_ms: float


class ElevatorResponse(BaseModel):
    """Response schema for elevator."""

    id: str
    max_capacity_kg: int
    created_at: datetime
    latest_health_score: float | None = None
    status: str | None = None


class AlertResponse(BaseModel):
    """Response schema for alert."""

    id: int | None = None
    elevator_id: str
    timestamp: datetime
    severity: str
    message: str
    acknowledged: int = 0
    acknowledged_by: str | None = None
    acknowledged_at: datetime | None = None


class MaintenanceResponse(BaseModel):
    """Response schema for maintenance schedule."""

    id: int | None = None
    elevator_id: str
    recommended_date: str
    urgency: str
    reason: str
    estimated_rul_hours: float | None = None
    status: str = "pending"
    completed_at: str | None = None
    technician: str | None = None
    created_at: datetime


class ModelReloadResponse(BaseModel):
    """Response schema for model reload."""

    status: str
    model: str
    version: str


class ErrorBlockResponse(BaseModel):
    """Response schema for a single error-history block."""

    index: int
    values: dict[str, int]  # address serialised as str for JSON compatibility


class ControllerSnapshotResponse(BaseModel):
    """Response schema for a controller telemetry snapshot."""

    id: int | None = None
    elevator_id: str
    slave_id: int
    timestamp: str  # UTC ISO-8601
    raw_values: dict[str, int]  # address serialised as str
    scaled_values: dict[str, float]  # address serialised as str
    error_blocks: list[ErrorBlockResponse]
    failed_addresses: list[int]
    synced: int | None = None

    @classmethod
    def from_domain(cls, snapshot: ControllerSnapshot) -> ControllerSnapshotResponse:
        """Convert a :class:`ControllerSnapshot` domain entity to this response schema."""
        return cls(
            id=snapshot.id,
            elevator_id=snapshot.elevator_id,
            slave_id=snapshot.slave_id,
            timestamp=snapshot.timestamp,
            raw_values={str(k): v for k, v in snapshot.raw_values.items()},
            scaled_values={str(k): v for k, v in snapshot.scaled_values.items()},
            error_blocks=[
                ErrorBlockResponse(
                    index=block.index,
                    values={str(k): v for k, v in block.values.items()},
                )
                for block in snapshot.error_blocks
            ],
            failed_addresses=list(snapshot.failed_addresses),
        )
