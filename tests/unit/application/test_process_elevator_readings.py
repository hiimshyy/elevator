"""Tests for ProcessElevatorReadingsUseCase."""

from elevator_pdm.application.use_cases.process_elevator_readings import (
    ProcessElevatorReadingsUseCase,
)
from elevator_pdm.domain.entities.alert import Alert
from elevator_pdm.domain.entities.elevator import Elevator
from elevator_pdm.domain.entities.inference_result import InferenceResult
from elevator_pdm.domain.entities.sensor_reading import SensorReading
from elevator_pdm.infrastructure.config.settings import Settings


class _FakeElevatorRepo:
    def get_by_id(self, elevator_id: str) -> Elevator | None:
        return Elevator(
            id=elevator_id,
            name="Test Elevator",
            location="Lab",
            max_capacity_kg=1000,
            install_date="2024-01-01",
        )


class _FakeReadingRepo:
    def __init__(self, readings: list[SensorReading]) -> None:
        self._readings = readings

    def find_by_elevator(self, elevator_id: str, **kwargs) -> list[SensorReading]:
        return [reading for reading in self._readings if reading.elevator_id == elevator_id]


class _FakeInferenceRepo:
    def __init__(self, latest: InferenceResult | None = None) -> None:
        self._latest = latest
        self.saved: list[InferenceResult] = []

    def save(self, result: InferenceResult) -> None:
        result.id = len(self.saved) + 1
        self.saved.append(result)
        self._latest = result

    def find_latest(self, elevator_id: str) -> InferenceResult | None:
        return self._latest

    def find_by_elevator(self, elevator_id: str, **kwargs) -> list[InferenceResult]:
        return [result for result in self.saved if result.elevator_id == elevator_id]


class _FakeAlertRepo:
    def __init__(self) -> None:
        self.saved: list[Alert] = []

    def save(self, alert: Alert) -> None:
        self.saved.append(alert)


class _FakeRuntime:
    def __init__(self, results: list[InferenceResult]) -> None:
        self._results = results
        self.model_version = "test-model"

    def predict(self, features: dict[str, float]) -> InferenceResult:
        return self._results.pop(0)


def test_processes_only_readings_newer_than_latest_inference() -> None:
    settings = Settings()
    latest = InferenceResult(
        elevator_id="elev-001",
        timestamp="2026-06-01T00:00:00+00:00",
        model_name="vibration_anomaly",
        model_version="old",
        status="NORMAL",
    )
    readings = [
        SensorReading(
            elevator_id="elev-001",
            sensor_id="ES-VS-01",
            timestamp="2026-06-01T00:00:00+00:00",
            accel_rms_mg=60.0,
        ),
        SensorReading(
            elevator_id="elev-001",
            sensor_id="ES-VS-01",
            timestamp="2026-06-01T00:05:00+00:00",
            accel_rms_mg=95.0,
        ),
    ]
    use_case = ProcessElevatorReadingsUseCase(
        elevator_repo=_FakeElevatorRepo(),
        reading_repo=_FakeReadingRepo(readings),
        inference_repo=_FakeInferenceRepo(latest=latest),
        alert_repo=_FakeAlertRepo(),
        model_runtime=_FakeRuntime(
            [
                InferenceResult(
                    elevator_id="",
                    timestamp="",
                    model_name="vibration_anomaly",
                    model_version="old",
                    status="WARNING",
                    confidence=0.8,
                )
            ]
        ),
        settings=settings,
    )

    summary = use_case.execute("elev-001")

    assert summary["processed_readings"] == 1
    assert summary["alerts_created"] == 1


def test_creates_emergency_alert_for_overload_status() -> None:
    alert_repo = _FakeAlertRepo()
    use_case = ProcessElevatorReadingsUseCase(
        elevator_repo=_FakeElevatorRepo(),
        reading_repo=_FakeReadingRepo(
            [
                SensorReading(
                    elevator_id="elev-001",
                    sensor_id="RW-ST01D",
                    timestamp="2026-06-01T01:00:00+00:00",
                    load_kg=980.0,
                )
            ]
        ),
        inference_repo=_FakeInferenceRepo(),
        alert_repo=alert_repo,
        model_runtime=_FakeRuntime(
            [
                InferenceResult(
                    elevator_id="",
                    timestamp="",
                    model_name="vibration_anomaly",
                    model_version="old",
                    status="OVERLOAD",
                    confidence=0.97,
                )
            ]
        ),
        settings=Settings(),
    )

    summary = use_case.execute("elev-001")

    assert summary["processed_readings"] == 1
    assert summary["alerts_created"] == 1
    assert alert_repo.saved[0].severity == "EMERGENCY"
    assert alert_repo.saved[0].alert_type == "OVERLOAD"
