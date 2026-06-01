"""Tests for SQLiteReadingRepo implementation."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from elevator_pdm.domain.entities.sensor_reading import SensorReading
from elevator_pdm.infrastructure.persistence.models import (
    Base,
    Elevator,
)
from elevator_pdm.infrastructure.persistence.models import (
    SensorReading as ORMSensorReading,
)
from elevator_pdm.infrastructure.persistence.sqlite_reading_repo import SQLiteReadingRepo


@pytest.fixture
def repo():
    """Create an in-memory SQLite repo with schema initialized."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_local = sessionmaker(bind=engine)
    session = session_local()

    # Create a test elevator first
    elevator = Elevator(
        id="test-elev-001",
        name="Test Elevator",
        location="Building A",
        max_capacity_kg=1000,
        install_date="2025-01-01"
    )
    session.add(elevator)
    session.commit()

    return SQLiteReadingRepo(session), session


def test_save_persists_reading_and_auto_increments_id(repo):
    repo, session = repo
    reading = SensorReading(
        elevator_id="test-elev-001",
        sensor_id="ES-VS-01",
        timestamp="2025-01-01T00:00:00+00:00",
        accel_rms_mg=42.5,
    )
    repo.save(reading)

    orm_readings = session.query(ORMSensorReading).all()
    assert len(orm_readings) == 1
    assert orm_readings[0].id == 1
    assert orm_readings[0].accel_rms_mg == 42.5


def test_find_by_elevator_filters_by_time_range(repo):
    repo, session = repo

    # Add readings at different times
    for i in range(5):
        reading = SensorReading(
            elevator_id="test-elev-001",
            sensor_id="ES-VS-01",
            timestamp=f"2025-01-01T00:0{i}:00+00:00",
            accel_rms_mg=float(i * 10),
        )
        repo.save(reading)

    results = repo.find_by_elevator(
        "test-elev-001",
        from_ts="2025-01-01T00:02:00+00:00",
        to_ts="2025-01-01T00:04:00+00:00",
    )
    assert len(results) == 3  # readings at 2, 3, 4 minutes


def test_find_by_elevator_filters_by_sensor_id(repo):
    repo, session = repo

    for sensor in ["ES-VS-01", "ES35-SW", "RW-ST01D"]:
        reading = SensorReading(
            elevator_id="test-elev-001",
            sensor_id=sensor,
            timestamp="2025-01-01T00:00:00+00:00",
        )
        repo.save(reading)

    results = repo.find_by_elevator("test-elev-001", sensor_id="ES-VS-01")
    assert len(results) == 1
    assert results[0].sensor_id == "ES-VS-01"


def test_find_by_elevator_respects_limit(repo):
    repo, session = repo

    for i in range(10):
        reading = SensorReading(
            elevator_id="test-elev-001",
            sensor_id="ES-VS-01",
            timestamp=f"2025-01-01T00:0{i}:00+00:00",
        )
        repo.save(reading)

    results = repo.find_by_elevator("test-elev-001", limit=5)
    assert len(results) == 5


def test_find_latest_returns_most_recent(repo):
    repo, session = repo

    reading1 = SensorReading(
        elevator_id="test-elev-001",
        sensor_id="ES-VS-01",
        timestamp="2025-01-01T00:00:00+00:00",
    )
    reading2 = SensorReading(
        elevator_id="test-elev-001",
        sensor_id="ES-VS-01",
        timestamp="2025-01-01T01:00:00+00:00",
    )
    repo.save(reading1)
    repo.save(reading2)

    latest = repo.find_latest("test-elev-001")
    assert latest is not None
    assert latest.timestamp == "2025-01-01T01:00:00+00:00"
    assert latest.id is not None
    assert latest.synced == 0


def test_find_latest_returns_none_for_unknown_elevator(repo):
    repo, session = repo
    result = repo.find_latest("nonexistent")
    assert result is None


def test_find_unsynced_returns_only_unsynced_rows(repo):
    repo, session = repo

    # Add 3 readings (all unsynced by default)
    for i in range(3):
        reading = SensorReading(
            elevator_id="test-elev-001",
            sensor_id="ES-VS-01",
            timestamp=f"2025-01-01T00:0{i}:00+00:00",
        )
        repo.save(reading)

    # Mark first reading as synced
    first_orm = session.query(ORMSensorReading).first()
    first_orm.synced = 1
    session.commit()

    unsynced = repo.find_unsynced()
    assert len(unsynced) == 2


def test_mark_synced_sets_synced_flag(repo):
    repo, session = repo

    # Add readings
    for i in range(3):
        reading = SensorReading(
            elevator_id="test-elev-001",
            sensor_id="ES-VS-01",
            timestamp=f"2025-01-01T00:0{i}:00+00:00",
        )
        repo.save(reading)

    # Get reading IDs and mark them as synced
    readings = session.query(ORMSensorReading).all()
    reading_ids = [r.id for r in readings]
    repo.mark_synced(reading_ids)

    unsynced = repo.find_unsynced()
    assert len(unsynced) == 0


def test_mark_synced_with_empty_list(repo):
    repo, session = repo
    # Should not raise
    repo.mark_synced([])
