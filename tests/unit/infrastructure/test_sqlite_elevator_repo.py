"""Tests for SQLiteElevatorRepo implementation."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from elevator_pdm.infrastructure.persistence.models import Base, Elevator as ORMElevator
from elevator_pdm.infrastructure.persistence.sqlite_elevator_repo import SQLiteElevatorRepo
from elevator_pdm.domain.entities.elevator import Elevator


@pytest.fixture
def repo():
    """Create an in-memory SQLite repo with schema initialized."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    return SQLiteElevatorRepo(session), session


def test_create_and_get_by_id(repo):
    repo, session = repo
    elevator = Elevator(
        id="test-elev-001",
        name="Test Elevator",
        location="Building A",
        max_capacity_kg=1000,
        install_date="2025-01-01",
    )
    repo.create(elevator)

    result = repo.get_by_id("test-elev-001")
    assert result is not None
    assert result.name == "Test Elevator"
    assert result.max_capacity_kg == 1000
    assert result.status == "active"


def test_get_by_id_returns_none_for_unknown(repo):
    repo, session = repo
    result = repo.get_by_id("nonexistent")
    assert result is None


def test_get_all_returns_all_elevators(repo):
    repo, session = repo

    for i in range(3):
        elevator = Elevator(
            id=f"test-elev-{i}",
            name=f"Elevator {i}",
            location="Building A",
            max_capacity_kg=1000,
            install_date="2025-01-01",
        )
        repo.create(elevator)

    results = repo.get_all()
    assert len(results) == 3


def test_update_elevator(repo):
    repo, session = repo
    elevator = Elevator(
        id="test-elev-001",
        name="Test Elevator",
        location="Building A",
        max_capacity_kg=1000,
        install_date="2025-01-01",
    )
    repo.create(elevator)

    # Update the elevator
    elevator.name = "Updated Elevator"
    elevator.status = "maintenance"
    repo.update(elevator)

    result = repo.get_by_id("test-elev-001")
    assert result.name == "Updated Elevator"
    assert result.status == "maintenance"


def test_delete_elevator(repo):
    repo, session = repo
    elevator = Elevator(
        id="test-elev-001",
        name="Test Elevator",
        location="Building A",
        max_capacity_kg=1000,
        install_date="2025-01-01",
    )
    repo.create(elevator)

    repo.delete("test-elev-001")

    result = repo.get_by_id("test-elev-001")
    assert result is None


def test_get_all_returns_empty_list_when_no_elevators(repo):
    repo, session = repo
    results = repo.get_all()
    assert len(results) == 0
