"""Sensor reading domain entity."""
from dataclasses import dataclass


@dataclass(frozen=True)
class SensorReading:
    """Immutable sensor data point from a single poll cycle."""

    elevator_id: str
    sensor_id: str  # ES-VS-01 | ES35-SW | RW-ST01D
    timestamp: str  # UTC ISO datetime

    # ES-VS-01 vibration fields
    accel_rms_mg: float | None = None
    velocity_rms_mms: float | None = None
    peak_accel_mg: float | None = None
    vib_temperature_c: float | None = None

    # ES35-SW environment fields
    env_temperature_c: float | None = None
    env_humidity_pct: float | None = None

    # RW-ST01D load field
    load_kg: float | None = None
    id: int | None = None
    synced: int = 0
