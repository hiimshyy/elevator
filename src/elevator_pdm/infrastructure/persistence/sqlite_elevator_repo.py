"""SQLite implementation of ElevatorRepository."""
from typing import List, Optional
from sqlalchemy.orm import Session

from elevator_pdm.domain.interfaces.elevator_repository import ElevatorRepository
from elevator_pdm.domain.entities.elevator import Elevator
from elevator_pdm.infrastructure.persistence.models import Elevator as ORMElevator


class SQLiteElevatorRepo(ElevatorRepository):
    """SQLite adapter for ElevatorRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def _to_orm(self, elevator: Elevator) -> ORMElevator:
        """Convert domain entity to ORM model."""
        return ORMElevator(
            id=elevator.id,
            name=elevator.name,
            location=elevator.location,
            max_capacity_kg=elevator.max_capacity_kg,
            install_date=elevator.install_date,
            last_maintenance=elevator.last_maintenance,
            status=elevator.status,
            created_at=elevator.created_at,
        )

    def _to_domain(self, orm_elevator: ORMElevator) -> Elevator:
        """Convert ORM model to domain entity."""
        return Elevator(
            id=orm_elevator.id,
            name=orm_elevator.name,
            location=orm_elevator.location,
            max_capacity_kg=orm_elevator.max_capacity_kg,
            install_date=orm_elevator.install_date,
            status=orm_elevator.status,
            last_maintenance=orm_elevator.last_maintenance,
            created_at=orm_elevator.created_at,
        )

    def create(self, elevator: Elevator) -> Optional[Elevator]:
        """Create a new elevator record. Returns created elevator or None if already exists."""
        # Check if already exists
        existing = self._session.query(ORMElevator).filter_by(id=elevator.id).first()
        if existing:
            return None
        orm_elevator = self._to_orm(elevator)
        self._session.add(orm_elevator)
        self._session.commit()
        return self._to_domain(orm_elevator)

    def get_by_id(self, elevator_id: str) -> Optional[Elevator]:
        """Get an elevator by ID."""
        orm_elevator = self._session.query(ORMElevator).filter_by(id=elevator_id).first()
        return self._to_domain(orm_elevator) if orm_elevator else None

    def get_all(self) -> List[Elevator]:
        """List all elevators."""
        return [self._to_domain(e) for e in self._session.query(ORMElevator).all()]

    def update(self, elevator: Elevator) -> None:
        """Update an existing elevator."""
        orm_elevator = self._session.query(ORMElevator).filter_by(id=elevator.id).first()
        if orm_elevator:
            orm_elevator.name = elevator.name
            orm_elevator.location = elevator.location
            orm_elevator.max_capacity_kg = elevator.max_capacity_kg
            orm_elevator.install_date = elevator.install_date
            orm_elevator.last_maintenance = elevator.last_maintenance
            orm_elevator.status = elevator.status
            self._session.commit()

    def delete(self, elevator_id: str) -> None:
        """Delete an elevator by ID."""
        self._session.query(ORMElevator).filter_by(id=elevator_id).delete()
        self._session.commit()
