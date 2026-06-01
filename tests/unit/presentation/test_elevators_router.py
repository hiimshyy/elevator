"""Regression tests for elevator API router."""

from datetime import UTC, datetime

import pytest
from fastapi import HTTPException

from elevator_pdm.presentation.api.routers.elevators import get_elevator, get_readings


class _FakeElevatorRepo:
    def get_by_id(self, elevator_id: str):
        return object() if elevator_id == "elev-001" else None


class _FakeReading:
    def __init__(self) -> None:
        self.id = 1
        self.elevator_id = "elev-001"
        self.timestamp = "2026-05-29T00:00:00+00:00"
        self.accel_rms_mg = 12.5
        self.velocity_rms_mms = 1.2
        self.peak_accel_mg = 20.1
        self.vib_temperature_c = 35.0
        self.env_temperature_c = 30.0
        self.env_humidity_pct = 60.0
        self.load_kg = 120.0
        self.synced = 0


class _FakeReadingRepo:
    def __init__(self) -> None:
        self.called_with = {}

    def find_by_elevator(self, elevator_id, from_ts=None, to_ts=None, sensor_id=None, limit=500):
        self.called_with = {
            "elevator_id": elevator_id,
            "from_ts": from_ts,
            "to_ts": to_ts,
            "sensor_id": sensor_id,
            "limit": limit,
        }
        return [_FakeReading()]


class _FakeInferenceRepo:
    def find_latest(self, elevator_id: str):
        return None


def test_get_readings_passes_from_ts_and_to_ts_and_returns_payload():
    repo = _FakeReadingRepo()
    elev_repo = _FakeElevatorRepo()
    from_time = datetime(2026, 5, 29, 0, 0, tzinfo=UTC)
    to_time = datetime(2026, 5, 29, 1, 0, tzinfo=UTC)

    result = get_readings(
        elevator_id="elev-001",
        from_time=from_time,
        to_time=to_time,
        sensor_id="ES-VS-01",
        limit=60,
        repo=repo,
        elev_repo=elev_repo,
    )

    assert len(result) == 1
    assert repo.called_with["elevator_id"] == "elev-001"
    assert repo.called_with["from_ts"] == from_time.isoformat()
    assert repo.called_with["to_ts"] == to_time.isoformat()
    assert repo.called_with["sensor_id"] == "ES-VS-01"
    assert repo.called_with["limit"] == 60


def test_get_elevator_returns_404_when_elevator_missing():
    elev_repo = _FakeElevatorRepo()
    inference_repo = _FakeInferenceRepo()

    with pytest.raises(HTTPException) as exc_info:
        get_elevator(
            elevator_id="missing-elevator",
            repo=elev_repo,
            inference_repo=inference_repo,
        )

    assert exc_info.value.status_code == 404
