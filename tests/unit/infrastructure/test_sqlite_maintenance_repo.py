"""Tests for SQLiteMaintenanceRepo implementation."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from elevator_pdm.domain.entities.maintenance import MaintenanceSchedule
from elevator_pdm.infrastructure.persistence.models import Base, Elevator
from elevator_pdm.infrastructure.persistence.models import MaintenanceSchedule as ORMaintenance
from elevator_pdm.infrastructure.persistence.sqlite_maintenance_repo import SQLiteMaintenanceRepo


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

    return SQLiteMaintenanceRepo(session), session


def test_create_and_find_by_elevator(repo):
    repo, session = repo
    maintenance = MaintenanceSchedule(
        elevator_id="test-elev-001",
        recommended_date="2025-02-01",
        urgency="routine",
        reason="Regular maintenance",
    )
    repo.create(maintenance)

    results = repo.find_by_elevator("test-elev-001")
    assert len(results) == 1
    assert results[0].urgency == "routine"
    assert results[0].status == "pending"


def test_find_by_elevator_filters_by_status(repo):
    repo, session = repo

    for status in ["pending", "scheduled", "completed", "pending"]:
        maintenance = MaintenanceSchedule(
            elevator_id="test-elev-001",
            recommended_date="2025-02-01",
            urgency="routine",
            reason="Test maintenance",
        )
        repo.create(maintenance)
        # Update status after creation
        orm_maint = session.query(ORMaintenance).all()[-1]
        repo.update_status(orm_maint.id, status)

    results = repo.find_by_elevator("test-elev-001", status="pending")
    assert len(results) == 2

    results = repo.find_by_elevator("test-elev-001", status="scheduled")
    assert len(results) == 1


def test_update_status_to_scheduled(repo):
    repo, session = repo

    maintenance = MaintenanceSchedule(
        elevator_id="test-elev-001",
        recommended_date="2025-02-01",
        urgency="urgent",
        reason="Urgent maintenance needed",
    )
    repo.create(maintenance)

    orm_maint = session.query(ORMaintenance).first()
    repo.update_status(orm_maint.id, "scheduled", completed_at="2025-02-15", technician="tech1")

    # Verify via ORM
    session.refresh(orm_maint)
    assert orm_maint.status == "scheduled"
    assert orm_maint.technician == "tech1"


def test_update_status_to_completed(repo):
    repo, session = repo

    maintenance = MaintenanceSchedule(
        elevator_id="test-elev-001",
        recommended_date="2025-02-01",
        urgency="routine",
        reason="Regular maintenance",
    )
    repo.create(maintenance)

    orm_maint = session.query(ORMaintenance).first()
    repo.update_status(orm_maint.id, "completed", completed_at="2025-02-10", technician="tech2")

    session.refresh(orm_maint)
    assert orm_maint.status == "completed"
    assert orm_maint.completed_at == "2025-02-10"


def test_find_by_elevator_returns_empty_for_unknown(repo):
    repo, session = repo
    results = repo.find_by_elevator("nonexistent")
    assert len(results) == 0


def test_status_transition_pending_to_scheduled(repo):
    repo, session = repo

    maintenance = MaintenanceSchedule(
        elevator_id="test-elev-001",
        recommended_date="2025-02-01",
        urgency="soon",
        reason="Maintenance soon",
    )
    repo.create(maintenance)

    orm_maint = session.query(ORMaintenance).first()
    assert orm_maint.status == "pending"

    repo.update_status(orm_maint.id, "scheduled")
    session.refresh(orm_maint)
    assert orm_maint.status == "scheduled"


def test_create_multiple_maintenance_records(repo):
    repo, session = repo

    for i in range(3):
        maintenance = MaintenanceSchedule(
            elevator_id="test-elev-001",
            recommended_date=f"2025-02-0{i+1}",
            urgency="routine",
            reason=f"Maintenance {i+1}",
        )
        repo.create(maintenance)

    results = repo.find_by_elevator("test-elev-001")
    assert len(results) == 3


def test_find_all_returns_all_records(repo):
    repo, session = repo

    for index in range(2):
        repo.create(
            MaintenanceSchedule(
                elevator_id="test-elev-001",
                recommended_date=f"2025-02-0{index + 1}",
                urgency="routine",
                reason=f"Maintenance {index + 1}",
            )
        )

    results = repo.find_all()

    assert len(results) == 2
    assert results[0].id is not None


def test_get_by_id_returns_record(repo):
    repo, session = repo
    repo.create(
        MaintenanceSchedule(
            elevator_id="test-elev-001",
            recommended_date="2025-02-01",
            urgency="routine",
            reason="Maintenance",
        )
    )

    orm_record = session.query(ORMaintenance).first()
    result = repo.get_by_id(orm_record.id)

    assert result is not None
    assert result.id == orm_record.id
