"""Tests for SQLiteAlertRepo implementation."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from elevator_pdm.domain.entities.alert import Alert
from elevator_pdm.infrastructure.persistence.models import Alert as ORMAlert
from elevator_pdm.infrastructure.persistence.models import Base, Elevator
from elevator_pdm.infrastructure.persistence.sqlite_alert_repo import SQLiteAlertRepo


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

    return SQLiteAlertRepo(session), session


def test_save_and_find_by_elevator(repo):
    repo, session = repo
    alert = Alert(
        elevator_id="test-elev-001",
        inference_id=1,
        alert_type="VIBRATION_HIGH",
        severity="WARNING",
        message="High vibration detected",
        sent_at="2025-01-01T00:00:00+00:00",
        channel="slack",
    )
    repo.save(alert)

    results = repo.find_by_elevator("test-elev-001")
    assert len(results) == 1
    assert results[0].severity == "WARNING"
    assert results[0].channel == "slack"


def test_find_by_elevator_filters_by_severity(repo):
    repo, session = repo

    for severity in ["WARNING", "CRITICAL", "WARNING"]:
        alert = Alert(
            elevator_id="test-elev-001",
            inference_id=1,
            alert_type="VIBRATION_HIGH",
            severity=severity,
            message="Test alert",
            sent_at="2025-01-01T00:00:00+00:00",
            channel="slack",
        )
        repo.save(alert)

    results = repo.find_by_elevator("test-elev-001", severity="WARNING")
    assert len(results) == 2

    results = repo.find_by_elevator("test-elev-001", severity="CRITICAL")
    assert len(results) == 1


def test_find_by_elevator_filters_by_acknowledged(repo):
    repo, session = repo

    # Create and acknowledge first alert
    alert1 = Alert(
        elevator_id="test-elev-001",
        inference_id=1,
        alert_type="VIBRATION_HIGH",
        severity="WARNING",
        message="Alert 1",
        sent_at="2025-01-01T00:00:00+00:00",
        channel="slack",
    )
    repo.save(alert1)
    orm_alert = session.query(ORMAlert).first()
    repo.acknowledge(orm_alert.id, "tech1")

    # Create second alert (not acknowledged)
    alert2 = Alert(
        elevator_id="test-elev-001",
        inference_id=1,
        alert_type="TEMP_HIGH",
        severity="CRITICAL",
        message="Alert 2",
        sent_at="2025-01-01T00:00:00+00:00",
        channel="email",
    )
    repo.save(alert2)

    results = repo.find_by_elevator("test-elev-001", acknowledged=True)
    assert len(results) == 1
    assert results[0].acknowledged is True

    results = repo.find_by_elevator("test-elev-001", acknowledged=False)
    assert len(results) == 1
    assert results[0].acknowledged is False


def test_acknowledge_sets_fields(repo):
    repo, session = repo

    alert = Alert(
        elevator_id="test-elev-001",
        inference_id=1,
        alert_type="VIBRATION_HIGH",
        severity="WARNING",
        message="Test alert",
        sent_at="2025-01-01T00:00:00+00:00",
        channel="slack",
    )
    repo.save(alert)

    orm_alert = session.query(ORMAlert).first()
    repo.acknowledge(orm_alert.id, "tech1")

    # Verify via ORM
    session.refresh(orm_alert)
    assert orm_alert.acknowledged == 1
    assert orm_alert.acknowledged_by == "tech1"
    assert orm_alert.acknowledged_at is not None


def test_find_by_elevator_returns_empty_for_unknown(repo):
    repo, session = repo
    results = repo.find_by_elevator("nonexistent")
    assert len(results) == 0


def test_find_all_returns_all_alerts(repo):
    repo, session = repo

    for severity in ["WARNING", "CRITICAL"]:
        repo.save(
            Alert(
                elevator_id="test-elev-001",
                inference_id=1,
                alert_type="VIBRATION_HIGH",
                severity=severity,
                message="Test alert",
                sent_at="2025-01-01T00:00:00+00:00",
                channel="slack",
            )
        )

    results = repo.find_all()

    assert len(results) == 2
    assert results[0].id is not None


def test_get_by_id_returns_alert(repo):
    repo, session = repo
    repo.save(
        Alert(
            elevator_id="test-elev-001",
            inference_id=1,
            alert_type="VIBRATION_HIGH",
            severity="WARNING",
            message="Test alert",
            sent_at="2025-01-01T00:00:00+00:00",
            channel="slack",
        )
    )

    orm_alert = session.query(ORMAlert).first()
    result = repo.get_by_id(orm_alert.id)

    assert result is not None
    assert result.id == orm_alert.id
