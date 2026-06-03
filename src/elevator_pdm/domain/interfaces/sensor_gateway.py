"""Sensor gateway interface (port)."""
from abc import ABC, abstractmethod
from typing import Any


class SensorGateway(ABC):
    """Abstract interface for reading sensor data from the RS-485 bus.

    Infrastructure layer provides concrete implementations:
    - ModbusGateway: real hardware via minimalmodbus
    - MockGateway: fake data for testing/development
    """

    @abstractmethod
    def read_vibration(self) -> dict[str, Any]:
        """Read ES-VS-01 vibration sensor.

        Returns:
            Dict with keys: sensor_id, accel_rms_mg, velocity_rms_mms,
            peak_accel_mg, temperature_c, timestamp
        """
        ...

    @abstractmethod
    def read_temp_humidity(self) -> dict[str, Any]:
        """Read ES35-SW temperature and humidity sensor.

        Returns:
            Dict with keys: sensor_id, temperature_c, humidity_pct, timestamp
        """
        ...

    @abstractmethod
    def read_load(self) -> dict[str, Any]:
        """Read RW-ST01D load cell via converter.

        Returns:
            Dict with keys: sensor_id, load_kg, timestamp
        """
        ...

    @abstractmethod
    def read_controller(self) -> dict[str, Any]:
        """Read additional elevator controller holding registers.

        Returns:
            Dict with keys: sensor_id, controller_register_1047,
            controller_register_0x2121, controller_register_0x2122, timestamp
        """
        ...
