"""Process persisted sensor readings into inference results and alerts."""
import logging
from typing import Any

from elevator_pdm.application.services.feature_engineer import FeatureEngineer
from elevator_pdm.application.use_cases.dispatch_alert import DispatchAlert
from elevator_pdm.application.use_cases.run_inference import RunInferenceUseCase
from elevator_pdm.domain.entities.inference_result import InferenceResult
from elevator_pdm.domain.entities.sensor_reading import SensorReading
from elevator_pdm.domain.interfaces.alert_repository import AlertRepository
from elevator_pdm.domain.interfaces.elevator_repository import ElevatorRepository
from elevator_pdm.domain.interfaces.inference_repository import InferenceRepository
from elevator_pdm.domain.interfaces.model_runtime import ModelRuntime
from elevator_pdm.domain.interfaces.mqtt_publisher import MqttPublisher
from elevator_pdm.domain.interfaces.reading_repository import ReadingRepository
from elevator_pdm.infrastructure.config.settings import Settings

logger = logging.getLogger(__name__)


class ProcessElevatorReadingsUseCase:
    """Generate inference results and alerts from stored readings."""

    def __init__(
        self,
        elevator_repo: ElevatorRepository,
        reading_repo: ReadingRepository,
        inference_repo: InferenceRepository,
        alert_repo: AlertRepository,
        model_runtime: ModelRuntime,
        settings: Settings | None = None,
        notifier: object | None = None,
        mqtt_publisher: MqttPublisher | None = None,
    ) -> None:
        self._elevator_repo = elevator_repo
        self._reading_repo = reading_repo
        self._inference_repo = inference_repo
        self._alert_repo = alert_repo
        self._model_runtime = model_runtime
        self._settings = settings or Settings()
        self._notifier = notifier
        self._mqtt_publisher = mqtt_publisher

    def execute(self, elevator_id: str, limit: int = 500) -> dict[str, int | str | None]:
        elevator = self._elevator_repo.get_by_id(elevator_id)
        max_capacity_kg = (
            elevator.max_capacity_kg
            if elevator is not None
            else self._settings.elevator.max_capacity_kg
        )
        feature_engineer = FeatureEngineer(max_capacity_kg=max_capacity_kg)
        inference_runner = RunInferenceUseCase(
            model_runtime=self._model_runtime,
            inference_repo=self._inference_repo,
            event_bus=None,
        )
        alert_dispatcher = DispatchAlert(
            alert_repo=self._alert_repo,
            notifier=self._notifier,
            settings=self._settings,
        )

        latest_inference = self._inference_repo.find_latest(elevator_id)
        latest_timestamp = latest_inference.timestamp if latest_inference else None

        readings = self._reading_repo.find_by_elevator(elevator_id, limit=limit)
        ordered_readings = sorted(readings, key=lambda reading: reading.timestamp)
        if latest_timestamp:
            ordered_readings = [
                reading for reading in ordered_readings if reading.timestamp > latest_timestamp
            ]

        processed = 0
        alerts_created = 0
        alerts_suppressed = 0
        last_status: str | None = latest_inference.status if latest_inference else None

        for reading in ordered_readings:
            features = feature_engineer.compute(self._reading_to_feature_input(reading))
            result = inference_runner.execute(
                elevator_id=elevator_id,
                features=features,
                timestamp=reading.timestamp,
            )
            processed += 1
            last_status = result.status
            self._publish_status(reading=reading, inference_result=result, alert_sent=False)

            if result.status == "NORMAL":
                continue

            alert_type, severity, message = self._build_alert_payload(
                reading=reading,
                inference_result=result,
                max_capacity_kg=max_capacity_kg,
            )
            dispatched, reason = alert_dispatcher.execute(
                elevator_id=elevator_id,
                severity=severity,
                message=message,
                timestamp=reading.timestamp,
                inference_id=result.id or 0,
                alert_type=alert_type,
            )
            if dispatched:
                alerts_created += 1
                self._publish_status(reading=reading, inference_result=result, alert_sent=True)
            elif reason == "rate_limited":
                alerts_suppressed += 1

        return {
            "elevator_id": elevator_id,
            "processed_readings": processed,
            "alerts_created": alerts_created,
            "alerts_suppressed": alerts_suppressed,
            "last_status": last_status,
            "last_inference_timestamp": latest_timestamp,
        }

    def _reading_to_feature_input(self, reading: SensorReading) -> dict[str, float | None]:
        return {
            "accel_rms_mg": reading.accel_rms_mg,
            "velocity_rms_mms": reading.velocity_rms_mms,
            "peak_accel_mg": reading.peak_accel_mg,
            "vib_temperature_c": reading.vib_temperature_c,
            "env_temperature_c": reading.env_temperature_c,
            "env_humidity_pct": reading.env_humidity_pct,
            "load_kg": reading.load_kg,
        }

    def _build_alert_payload(
        self,
        reading: SensorReading,
        inference_result: InferenceResult,
        max_capacity_kg: float,
    ) -> tuple[str, str, str]:
        thresholds = self._settings.thresholds
        load_pct = (reading.load_kg / max_capacity_kg) if reading.load_kg is not None else 0.0
        vib_temp = reading.vib_temperature_c
        accel_rms = reading.accel_rms_mg

        if inference_result.status == "OVERLOAD" or load_pct >= thresholds.load_overload_pct:
            return (
                "OVERLOAD",
                "EMERGENCY",
                (
                    f"Overload detected for {reading.elevator_id}: "
                    f"load={reading.load_kg or 0:.1f} kg ({load_pct * 100:.1f}% of capacity)"
                ),
            )

        if vib_temp is not None and vib_temp >= thresholds.motor_temp_critical_c:
            return (
                "TEMP_HIGH",
                "CRITICAL",
                f"Motor temperature {vib_temp:.1f} C exceeded critical threshold",
            )

        if vib_temp is not None and vib_temp >= thresholds.motor_temp_warning_c:
            return (
                "TEMP_HIGH",
                "WARNING",
                f"Motor temperature {vib_temp:.1f} C exceeded warning threshold",
            )

        if accel_rms is not None and accel_rms >= thresholds.accel_rms_critical_mg:
            return (
                "VIBRATION_HIGH",
                "CRITICAL",
                f"Acceleration RMS {accel_rms:.1f} mg exceeded critical threshold",
            )

        if accel_rms is not None and accel_rms >= thresholds.accel_rms_warning_mg:
            return (
                "VIBRATION_HIGH",
                "WARNING",
                f"Acceleration RMS {accel_rms:.1f} mg exceeded warning threshold",
            )

        severity = "CRITICAL" if inference_result.status == "CRITICAL" else "WARNING"
        health_score_text = (
            f"{inference_result.health_score:.1f}"
            if inference_result.health_score is not None
            else "N/A"
        )
        return (
            "HEALTH_LOW",
            severity,
            (
                f"{inference_result.status} condition detected for {reading.elevator_id} "
                f"(confidence={inference_result.confidence:.2f}, health_score={health_score_text})"
            ),
        )

    def _publish_status(
        self,
        *,
        reading: SensorReading,
        inference_result: InferenceResult,
        alert_sent: bool,
    ) -> None:
        if self._mqtt_publisher is None:
            return

        payload: dict[str, Any] = {
            "event": "inference_result",
            "elevator_id": reading.elevator_id,
            "sensor_id": reading.sensor_id,
            "timestamp": reading.timestamp,
            "status": inference_result.status,
            "confidence": inference_result.confidence,
            "health_score": inference_result.health_score,
            "alert_sent": alert_sent,
            "reading": self._reading_to_feature_input(reading),
        }
        try:
            published = self._mqtt_publisher.publish_status(payload)
            if not published:
                logger.warning("MQTT status publish returned false for %s", reading.elevator_id)
        except Exception as exc:
            logger.warning("MQTT status publish failed for %s: %s", reading.elevator_id, exc)
