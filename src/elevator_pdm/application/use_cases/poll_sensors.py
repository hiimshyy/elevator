"""Poll sensors use case — orchestrates sensor reads, persistence, and queuing."""
import logging
from dataclasses import asdict
from datetime import UTC, datetime

from elevator_pdm.domain.entities.sensor_reading import SensorReading
from elevator_pdm.domain.exceptions import SensorUnavailableError
from elevator_pdm.domain.interfaces.reading_repository import ReadingRepository
from elevator_pdm.domain.interfaces.sensor_gateway import SensorGateway
from elevator_pdm.infrastructure.messaging.redis_queue import RedisQueue

logger = logging.getLogger(__name__)


class PollSensorsUseCase:
    """Orchestrates: poll sensors → save to repo → enqueue to Redis.

    Per-sensor error handling with exponential backoff.
    """

    def __init__(
        self,
        sensor_gateway: SensorGateway,
        reading_repo: ReadingRepository,
        redis_queue: RedisQueue,
        mqtt_publisher: object | None = None,
    ) -> None:
        self._gateway = sensor_gateway
        self._reading_repo = reading_repo
        self._redis_queue = redis_queue
        self._mqtt_publisher = mqtt_publisher

        # Track consecutive errors per sensor for backoff
        self._consecutive_errors = {
            "vibration": 0,
            "temp_humidity": 0,
            "load": 0,
        }
        self._max_backoff = 60  # seconds

    def _backoff_delay(self, sensor_key: str) -> float:
        """Calculate exponential backoff delay for a sensor."""
        errors = self._consecutive_errors[sensor_key]
        if errors == 0:
            return 0.0
        delay = min(2 ** (errors - 1), self._max_backoff)
        return float(delay)

    def _poll_one(
        self,
        sensor_key: str,
        read_method,
        elevator_id: str,
    ) -> SensorReading | None:
        """Poll a single sensor with error handling and backoff tracking."""
        try:
            data = read_method()
            self._consecutive_errors[sensor_key] = 0  # Reset on success

            # Build SensorReading entity
            reading = SensorReading(
                elevator_id=elevator_id,
                sensor_id=data.get("sensor_id", ""),
                timestamp=data.get("timestamp", datetime.now(UTC).isoformat()),
                accel_rms_mg=data.get("accel_rms_mg"),
                velocity_rms_mms=data.get("velocity_rms_mms"),
                peak_accel_mg=data.get("peak_accel_mg"),
                vib_temperature_c=data.get("temperature_c") if sensor_key == "vibration" else None,
                env_temperature_c=(
                    data.get("temperature_c") if sensor_key == "temp_humidity" else None
                ),
                env_humidity_pct=data.get("humidity_pct"),
                load_kg=data.get("load_kg"),
            )
            return reading
        except (SensorUnavailableError, Exception):
            self._consecutive_errors[sensor_key] += 1
            return None

    def execute(self, elevator_id: str = "elev-001") -> dict:
        """Poll all sensors, persist readings, and enqueue to Redis.

        Returns:
            Dict with keys: success (list of sensor_ids), failed (list of sensor_keys)
        """
        results = {"success": [], "failed": []}

        # Poll vibration sensor
        reading = self._poll_one("vibration", self._gateway.read_vibration, elevator_id)
        if reading:
            self._reading_repo.save(reading)
            payload = asdict(reading)
            self._redis_queue.enqueue(payload)
            self._publish_reading(payload)
            results["success"].append("ES-VS-01")
        else:
            results["failed"].append("vibration")

        # Poll temp/humidity sensor
        reading = self._poll_one("temp_humidity", self._gateway.read_temp_humidity, elevator_id)
        if reading:
            self._reading_repo.save(reading)
            payload = asdict(reading)
            self._redis_queue.enqueue(payload)
            self._publish_reading(payload)
            results["success"].append("ES35-SW")
        else:
            results["failed"].append("temp_humidity")

        # Poll load sensor
        reading = self._poll_one("load", self._gateway.read_load, elevator_id)
        if reading:
            self._reading_repo.save(reading)
            payload = asdict(reading)
            self._redis_queue.enqueue(payload)
            self._publish_reading(payload)
            results["success"].append("RW-ST01D")
        else:
            results["failed"].append("load")

        return results

    def get_backoff_status(self) -> dict:
        """Get current backoff status for all sensors."""
        return {
            key: {
                "consecutive_errors": errors,
                "current_backoff_s": self._backoff_delay(key),
            }
            for key, errors in self._consecutive_errors.items()
        }

    def _publish_reading(self, payload: dict) -> None:
        if self._mqtt_publisher is None:
            return

        try:
            published = self._mqtt_publisher.publish_reading(payload)
            if not published:
                logger.warning(
                    "MQTT reading publish returned false for %s", payload.get("sensor_id")
                )
        except Exception as exc:
            logger.warning(
                "MQTT reading publish failed for %s: %s", payload.get("sensor_id"), exc
            )
