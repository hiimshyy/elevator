"""Sensor ID value object."""
from enum import Enum


class SensorId(str, Enum):
    """Unique sensor identifiers on the RS-485 bus."""

    ES_VS_01 = "ES-VS-01"   # Vibration 3-axis
    ES35_SW = "ES35-SW"      # Temperature + Humidity
    RW_ST01D = "RW-ST01D"    # Load cell converter
