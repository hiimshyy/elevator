"""Mock sensor gateway for testing and development."""
import random
from datetime import UTC, datetime
from typing import Any

from elevator_pdm.domain.exceptions import SensorUnavailableError
from elevator_pdm.domain.interfaces.sensor_gateway import SensorGateway


class MockGateway(SensorGateway):
    """Simulates RS-485 Modbus sensors with reproducible random data.

    Supports a configurable seed for deterministic test runs.
    """

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)

    def read_vibration(self) -> dict[str, Any]:
        """Simulate ES-VS-01 vibration sensor reading."""
        try:
            return {
                "sensor_id": "ES-VS-01",
                "accel_rms_mg": self._rng.uniform(0, 500),
                "velocity_rms_mms": self._rng.uniform(0, 50),
                "peak_accel_mg": self._rng.uniform(0, 800),
                "temperature_c": self._rng.uniform(-10, 100),
                "timestamp": datetime.now(UTC).isoformat(),
            }
        except Exception as e:
            raise SensorUnavailableError(f"Vibration sensor unavailable: {e}") from e

    def read_temp_humidity(self) -> dict[str, Any]:
        """Simulate ES35-SW temperature and humidity sensor reading."""
        try:
            return {
                "sensor_id": "ES35-SW",
                "temperature_c": self._rng.uniform(-10, 100),
                "humidity_pct": self._rng.uniform(0, 100),
                "timestamp": datetime.now(UTC).isoformat(),
            }
        except Exception as e:
            raise SensorUnavailableError(f"Temp/humidity sensor unavailable: {e}") from e

    def read_load(self) -> dict[str, Any]:
        """Simulate RW-ST01D + HD-MV01A load cell reading."""
        try:
            return {
                "sensor_id": "RW-ST01D",
                "load_kg": self._rng.uniform(0, 2000),
                "timestamp": datetime.now(UTC).isoformat(),
            }
        except Exception as e:
            raise SensorUnavailableError(f"Load cell sensor unavailable: {e}") from e

    def read_controller(self) -> dict[str, Any]:
        """Simulate additional elevator controller registers."""
        try:
            return {
                "sensor_id": "CTRL-485-01",
                "controller_register_1047": self._rng.randint(0, 65535),
                "controller_register_0x2121": self._rng.randint(0, 65535),
                "controller_register_0x2122": self._rng.randint(0, 65535),
                "timestamp": datetime.now(UTC).isoformat(),
            }
        except Exception as e:
            raise SensorUnavailableError(f"Controller registers unavailable: {e}") from e
