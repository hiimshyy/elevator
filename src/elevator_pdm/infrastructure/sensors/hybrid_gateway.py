"""Hybrid gateway: real elevator controller + mock external sensors."""

from typing import Any

from elevator_pdm.domain.interfaces.sensor_gateway import SensorGateway
from elevator_pdm.infrastructure.config.settings import Settings
from elevator_pdm.infrastructure.sensors.mock_gateway import MockGateway
from elevator_pdm.infrastructure.sensors.modbus_gateway import ModbusGateway


class HybridGateway(SensorGateway):
    """Uses the real RS-485 controller while simulating not-yet-installed sensors."""

    def __init__(
        self,
        settings: Settings | None = None,
        seed: int | None = None,
    ) -> None:
        self._settings = settings or Settings()
        self._mock_gateway = MockGateway(seed=seed)
        self._modbus_gateway = ModbusGateway(
            settings=self._settings,
            enabled_sensors={"controller"},
        )

    def read_vibration(self) -> dict[str, Any]:
        return self._mock_gateway.read_vibration()

    def read_temp_humidity(self) -> dict[str, Any]:
        return self._mock_gateway.read_temp_humidity()

    def read_load(self) -> dict[str, Any]:
        return self._mock_gateway.read_load()

    def read_controller(self) -> dict[str, Any]:
        return self._modbus_gateway.read_controller()
