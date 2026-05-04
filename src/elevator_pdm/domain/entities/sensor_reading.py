"""Sensor reading domain entity."""
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class SensorReading:
    """Immutable sensor data point from a single poll cycle."""

    elevator_id: str
    sensor_id: str  # ES-VS-01 | ES35-SW | RW-ST01D
    timestamp: str  # UTC ISO datetime

    # ES-VS-01 vibration fields
    accel_rms_mg: Optional[float] = None
    velocity_rms_mms: Optional[float] = None
    peak_accel_mg: Optional[float] = None
    vib_temperature_c: Optional[float] = None

    # ES35-SW environment fields
    env_temperature_c: Optional[float] = None
    env_humidity_pct: Optional[float] = None

    # RW-ST01D load field
    load_kg: Optional[float] = None
