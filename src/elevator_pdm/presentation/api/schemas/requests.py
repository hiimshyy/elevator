"""Pydantic request schemas for API."""
from pydantic import BaseModel, Field, validator
from typing import Optional


class CreateElevatorRequest(BaseModel):
    """Request schema for creating an elevator."""

    id: str = Field(..., description="Elevator identifier (e.g., elev-001)")
    name: str = Field(..., description="Elevator name")
    location: str = Field(..., description="Elevator location")
    max_capacity_kg: float = Field(..., description="Maximum load capacity in kg")
    install_date: str = Field(..., description="Installation date (ISO format)")


class SensorReadingRequest(BaseModel):
    """Request schema for sensor readings."""

    accel_rms_mg: float = Field(..., description="RMS acceleration in mg")
    velocity_rms_mms: Optional[float] = Field(None, description="RMS velocity in mm/s")
    peak_accel_mg: Optional[float] = Field(None, description="Peak acceleration in mg")
    vib_temperature_c: Optional[float] = Field(None, description="Vibration motor temperature in °C")
    env_temperature_c: Optional[float] = Field(None, description="Environment temperature in °C")
    env_humidity_pct: Optional[float] = Field(None, description="Environment humidity in %")
    load_kg: Optional[float] = Field(None, description="Load weight in kg")

    @validator('accel_rms_mg')
    def accel_rms_must_be_positive(cls, v):
        if v < 0:
            raise ValueError('accel_rms_mg must be non-negative')
        return v

    @validator('load_kg')
    def load_must_be_non_negative(cls, v):
        if v is not None and v < 0:
            raise ValueError('load_kg must be non-negative')
        return v


class PredictRequest(BaseModel):
    """Request schema for prediction endpoint."""

    elevator_id: str = Field(..., description="Elevator identifier")
    readings: SensorReadingRequest = Field(..., description="Sensor readings")


class MaintenanceRequest(BaseModel):
    """Request schema for creating maintenance entry."""

    elevator_id: str = Field(..., description="Elevator identifier")
    recommended_date: str = Field(..., description="ISO date for maintenance")
    urgency: str = Field(..., description="routine | soon | urgent | immediate")
    reason: str = Field(..., description="Reason for maintenance recommendation")

    @validator('urgency')
    def urgency_must_be_valid(cls, v):
        if v not in ['routine', 'soon', 'urgent', 'immediate']:
            raise ValueError('urgency must be one of: routine, soon, urgent, immediate')
        return v


class AlertAcknowledgeRequest(BaseModel):
    """Request schema for acknowledging alerts."""

    technician: str = Field(..., description="Name of technician")
