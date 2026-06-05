from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

import minimalmodbus
import serial

from elevator_pdm.domain.exceptions import SensorUnavailableError
from elevator_pdm.domain.interfaces.sensor_gateway import SensorGateway
from elevator_pdm.infrastructure.config.settings import Settings


class ModbusGateway(SensorGateway):
    """Reads sensors via RS-485 Modbus RTU using minimalmodbus.

    Sensor register map (verify against datasheet before deployment):
    - Elevator controller (slave 1):
        Reg 1047: controller-specific 16-bit value
        Reg 0x2121: controller-specific 16-bit value
        Reg 0x2122: controller-specific 16-bit value
    - ES-VS-01 (vibration, slave 2):
        Reg 0x00: accel_rms_mg (32-bit float)
        Reg 0x02: velocity_rms_mms (32-bit float)
        Reg 0x04: peak_accel_mg (32-bit float)
        Reg 0x06: temperature_c (32-bit float)
    - ES35-SW (temp/humidity, slave 3):
        Reg 0x00: temperature_c (32-bit float)
        Reg 0x02: humidity_pct (32-bit float)
    - RW-ST01D (load cell, slave 4):
        Reg 0x00: load_kg (32-bit float)
    """

    _PARITY_MAP = {
        "N": serial.PARITY_NONE,
        "E": serial.PARITY_EVEN,
        "O": serial.PARITY_ODD,
    }
    _BYTESIZE_MAP = {
        5: serial.FIVEBITS,
        6: serial.SIXBITS,
        7: serial.SEVENBITS,
        8: serial.EIGHTBITS,
    }
    _STOPBITS_MAP = {
        1: serial.STOPBITS_ONE,
        2: serial.STOPBITS_TWO,
    }

    def __init__(
        self,
        settings: Settings | None = None,
        enabled_sensors: Iterable[str] | None = None,
    ) -> None:
        self._settings = settings or Settings()
        self._enabled_sensors = set(
            enabled_sensors or ("vibration", "temp_humidity", "load", "controller")
        )
        port = self._settings.serial.port

        self._vib = self._build_instrument(
            port, self._settings.sensors.vibration.slave_id, "vibration"
        )
        self._temp = self._build_instrument(
            port, self._settings.sensors.temp_humid.slave_id, "temp_humidity"
        )
        self._load = self._build_instrument(
            port, self._settings.sensors.load.slave_id, "load"
        )
        self._controller = self._build_instrument(
            port, self._settings.controller.slave_id, "controller"
        )

    def _build_instrument(
        self,
        port: str,
        slave_id: int,
        sensor_name: str,
    ) -> minimalmodbus.Instrument | None:
        if sensor_name not in self._enabled_sensors:
            return None

        instrument = minimalmodbus.Instrument(port, slave_id)
        self._configure_instrument(instrument)
        return instrument

    def _configure_instrument(self, instrument: minimalmodbus.Instrument | None) -> None:
        if instrument is None:
            return
        assert instrument.serial is not None
        instrument.serial.baudrate = self._settings.serial.baudrate
        instrument.serial.timeout = self._settings.serial.timeout_s
        instrument.serial.bytesize = self._BYTESIZE_MAP[self._settings.serial.bytesize]
        instrument.serial.parity = self._PARITY_MAP[self._settings.serial.parity.upper()]
        instrument.serial.stopbits = self._STOPBITS_MAP[self._settings.serial.stopbits]

    def _require_instrument(
        self,
        instrument: minimalmodbus.Instrument | None,
        sensor_name: str,
    ) -> minimalmodbus.Instrument:
        if instrument is None:
            raise SensorUnavailableError(f"{sensor_name} is not enabled in this gateway")
        return instrument

    def _read_float(self, instrument: minimalmodbus.Instrument, register: int) -> float:
        """Read a 32-bit float from two consecutive 16-bit registers."""
        return instrument.read_float(register, functioncode=3)

    def _read_register(self, instrument: minimalmodbus.Instrument, register: int) -> int:
        """Read a single unsigned holding register."""
        return int(instrument.read_register(register, functioncode=3, signed=False))

    def read_vibration(self) -> dict[str, Any]:
        try:
            instrument = self._require_instrument(self._vib, "Vibration sensor")
            return {
                "sensor_id": "ES-VS-01",
                "accel_rms_mg": self._read_float(instrument, 0x00),
                "velocity_rms_mms": self._read_float(instrument, 0x02),
                "peak_accel_mg": self._read_float(instrument, 0x04),
                "temperature_c": self._read_float(instrument, 0x06),
                "timestamp": datetime.now(UTC).isoformat(),
            }
        except (minimalmodbus.NoResponseError, minimalmodbus.InvalidResponseError, OSError) as e:
            raise SensorUnavailableError(f"Vibration sensor unavailable: {e}") from e

    def read_temp_humidity(self) -> dict[str, Any]:
        try:
            instrument = self._require_instrument(self._temp, "Temp/humidity sensor")
            return {
                "sensor_id": "ES35-SW",
                "temperature_c": self._read_float(instrument, 0x00),
                "humidity_pct": self._read_float(instrument, 0x02),
                "timestamp": datetime.now(UTC).isoformat(),
            }
        except (minimalmodbus.NoResponseError, minimalmodbus.InvalidResponseError, OSError) as e:
            raise SensorUnavailableError(f"Temp/humidity sensor unavailable: {e}") from e

    def read_load(self) -> dict[str, Any]:
        try:
            instrument = self._require_instrument(self._load, "Load cell")
            return {
                "sensor_id": "RW-ST01D",
                "load_kg": self._read_float(instrument, 0x00),
                "timestamp": datetime.now(UTC).isoformat(),
            }
        except (minimalmodbus.NoResponseError, minimalmodbus.InvalidResponseError, OSError) as e:
            raise SensorUnavailableError(f"Load cell sensor unavailable: {e}") from e

    def read_controller(self) -> dict[str, Any]:
        try:
            instrument = self._require_instrument(self._controller, "Controller registers")
            return {
                "sensor_id": self._settings.controller.sensor_id,
                "controller_register_1047": self._read_register(
                    instrument, self._settings.controller.register_1047
                ),
                "controller_register_0x2121": self._read_register(
                    instrument, self._settings.controller.register_0x2121
                ),
                "controller_register_0x2122": self._read_register(
                    instrument, self._settings.controller.register_0x2122
                ),
                "timestamp": datetime.now(UTC).isoformat(),
            }
        except (minimalmodbus.NoResponseError, minimalmodbus.InvalidResponseError, OSError) as e:
            raise SensorUnavailableError(f"Controller registers unavailable: {e}") from e
