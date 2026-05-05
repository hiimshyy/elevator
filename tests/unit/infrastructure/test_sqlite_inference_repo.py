"""Tests for SQLiteInferenceRepo implementation."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from elevator_pdm.infrastructure.persistence.models import Base, Elevator, InferenceResult as ORMInferenceResult
from elevator_pdm.infrastructure.persistence.sqlite_inference_repo import SQLiteInferenceRepo
from elevator_pdm.domain.entities.inference_result import InferenceResult


@pytest.fixture
def repo():
    """Create an in-memory SQLite repo with schema initialized."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    # Create a test elevator first
    elevator = Elevator(
        id="test-elev-001",
        name="Test Elevator",
        location="Building A",
        max_capacity_kg=1000,
        install_date="2025-01-01",
    )
    session.add(elevator)
    session.commit()

    return SQLiteInferenceRepo(session), session


def test_save_and_find_by_elevator(repo):
    repo, session = repo
    result = InferenceResult(
        elevator_id="test-elev-001",
        timestamp="2025-01-01T00:00:00+00:00",
        model_name="vibration_anomaly",
        model_version="1.0",
        status="NORMAL",
        confidence=0.95,
        health_score=85.0,
    )
    repo.save(result)

    results = repo.find_by_elevator("test-elev-001")
    assert len(results) == 1
    assert results[0].status == "NORMAL"
    assert results[0].confidence == 0.95


def test_find_by_elevator_filters_by_time_range(repo):
    repo, session = repo

    for i in range(5):
        result = InferenceResult(
            elevator_id="test-elev-001",
            timestamp=f"2025-01-01T00:0{i}:00+00:00",
            model_name="vibration_anomaly",
            model_version="1.0",
            status="NORMAL",
        )
        repo.save(result)

    results = repo.find_by_elevator(
        "test-elev-001",
        from_ts="2025-01-01T00:02:00+00:00",
        to_ts="2025-01-01T00:04:00+00:00",
    )
    assert len(results) == 3


def test_find_by_elevator_filters_by_status(repo):
    repo, session = repo

    for status in ["NORMAL", "WARNING", "CRITICAL", "NORMAL"]:
        result = InferenceResult(
            elevator_id="test-elev-001",
            timestamp="2025-01-01T00:00:00+00:00",
            model_name="vibration_anomaly",
            model_version="1.0",
            status=status,
        )
        repo.save(result)

    results = repo.find_by_elevator("test-elev-001", status="NORMAL")
    assert len(results) == 2

    results = repo.find_by_elevator("test-elev-001", status="WARNING")
    assert len(results) == 1


def test_find_latest_returns_most_recent(repo):
    repo, session = repo

    result1 = InferenceResult(
        elevator_id="test-elev-001",
        timestamp="2025-01-01T00:00:00+00:00",
        model_name="vibration_anomaly",
        model_version="1.0",
        status="NORMAL",
    )
    result2 = InferenceResult(
        elevator_id="test-elev-001",
        timestamp="2025-01-01T01:00:00+00:00",
        model_name="vibration_anomaly",
        model_version="1.0",
        status="WARNING",
    )
    repo.save(result1)
    repo.save(result2)

    latest = repo.find_latest("test-elev-001")
    assert latest is not None
    assert latest.timestamp == "2025-01-01T01:00:00+00:00"
    assert latest.status == "WARNING"


def test_find_latest_returns_none_for_unknown_elevator(repo):
    repo, session = repo
    result = repo.find_latest("nonexistent")
    assert result is None


def test_save_multiple_results_for_same_elevator(repo):
    repo, session = repo

    for i in range(5):
        result = InferenceResult(
            elevator_id="test-elev-001",
            timestamp=f"2025-01-01T00:0{i}:00+00:00",
            model_name="vibration_anomaly",
            model_version="1.0",
            status="NORMAL",
        )
        repo.save(result)

    results = repo.find_by_elevator("test-elev-001")
    assert len(results) == 5
