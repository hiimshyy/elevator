"""Elevator repository interface (port)."""
from abc import ABC, abstractmethod
from typing import List, Optional

from elevator_pdm.domain.entities.elevator import Elevator


class ElevatorRepository(ABC):
    """Abstract interface for elevator CRUD operations."""

    @abstractmethod
    def create(self, elevator: Elevator) -> None:
        """Create a new elevator record."""
        ...

    @abstractmethod
    def get_by_id(self, elevator_id: str) -> Optional[Elevator]:
        """Get an elevator by ID."""
        ...

    @abstractmethod
    def get_all(self) -> List[Elevator]:
        """List all elevators."""
        ...

    @abstractmethod
    def update(self, elevator: Elevator) -> None:
        """Update an existing elevator."""
        ...

    @abstractmethod
    def delete(self, elevator_id: str) -> None:
        """Delete an elevator by ID."""
        ...
