"""Modbus RTU sensor gateway for real hardware."""
import minimalmodbus
from typing import Dict, Any
from datetime import datetime, timezone

from elevator_pdm.domain.interfaces.sensor_gateway import SensorGateway
from elevator_pdm.domain.exceptions import SensorUnavailableError
from elevator_pdm.infrastructure.config.settings import Settings


class ModbusGateway(SensorGateway):
    """Reads sensors via RS-485 Modbus RTU using minimalmodbus.

    Sensor register map (verify against datasheet before deployment):
    - ES-VS-01 (vibration, slave 1):
        Reg 0x00: accel_rms_mg (32-bit float)
        Reg 0x02: velocity_rms_mms (32-bit float)
        Reg 0x04: peak_accel_mg (32-bit float)
        Reg 0x06: temperature_c (32-bit float)
    - ES35-SW (temp/humidity, slave 2):
        Reg 0x00: temperature_c (32-bit float)
        Reg 0x02: humidity_pct (32-bit float)
    - RW-ST01D (load cell, slave 3):
        Reg 0x00: load_kg (32-bit float)
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or Settings()
        port = self._settings.serial.port
        baud = self._settings.serial.baudrate
        timeout = self._settings.serial.timeout_s

        self._vib = minimalmodbus.Instrument(port, self._settings.sensors.vibration.slave_id)
        self._vib.serial.baudrate = baud
        self._vib.serial.timeout = timeout

        self._temp = minimalmodbus.Instrument(port, self._settings.sensors.temp_humid.slave_id)
        self._temp.serial.baudrate = baud
        self._temp.serial.timeout = timeout

        self._load = minimalmodbus.Instrument(port, self._settings.sensors.load.slave_id)
        self._load.serial.baudrate = baud
        self._load.serial.timeout = timeout

    def _read_float(self, instrument: minimalmodbus.Instrument, register: int) -> float:
        """Read a 32-bit float from two consecutive 16-bit registers."""
        return instrument.read_float(register, functioncode=3)

    def read_vibration(self) -> Dict[str, Any]:
        try:
            return {
                "sensor_id": "ES-VS-01",
                "accel_rms_mg": self._read_float(self._vib, 0x00),
                "velocity_rms_mms": self._read_float(self._vib, 0x02),
                "peak_accel_mg": self._read_float(self._vib, 0x04),
                "temperature_c": self._read_float(self._vib, 0x06),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except (minimalmodbus.NoResponseError, minimalmodbus.InvalidResponseError, OSError) as e:
            raise SensorUnavailableError(f"Vibration sensor unavailable: {e}") from e

    def read_temp_humidity(self) -> Dict[str, Any]:
        try:
            return {
                "sensor_id": "ES35-SW",
                "temperature_c": self._read_float(self._temp, 0x00),
                "humidity_pct": self._read_float(self._temp, 0x02),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except (minimalmodbus.NoResponseError, minimalmodbus.InvalidResponseError, OSError) as e:
            raise SensorUnavailableError(f"Temp/humidity sensor unavailable: {e}") from e

    def read_load(self) -> Dict[str, Any]:
        try:
            return {
                "sensor_id": "RW-ST01D",
                "load_kg": self._read_float(self._load, 0x00),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except (minimalmodbus.NoResponseError, minimalmodbus.InvalidResponseError, OSError) as e:
            raise SensorUnavailableError(f"Load cell sensor unavailable: {e}") from e
