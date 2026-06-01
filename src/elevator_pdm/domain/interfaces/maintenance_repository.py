"""Maintenance repository interface (port)."""
from abc import ABC, abstractmethod

from elevator_pdm.domain.entities.maintenance import MaintenanceSchedule


class MaintenanceRepository(ABC):
    """Abstract interface for maintenance schedule operations."""

    @abstractmethod
    def create(self, maintenance: MaintenanceSchedule) -> None:
        """Create a maintenance schedule entry."""
        ...

    @abstractmethod
    def find_by_elevator(
        self,
        elevator_id: str,
        status: str | None = None,
    ) -> list[MaintenanceSchedule]:
        """Query maintenance records for an elevator with optional status filter."""
        ...

    @abstractmethod
    def find_all(self, status: str | None = None) -> list[MaintenanceSchedule]:
        """Query maintenance records across all elevators."""
        ...

    @abstractmethod
    def get_by_id(self, maintenance_id: int) -> MaintenanceSchedule | None:
        """Get a single maintenance record by its database ID."""
        ...

    @abstractmethod
    def update_status(self, maintenance_id: int, status: str, **kwargs) -> None:
        """Update maintenance status and optional fields (completed_at, technician)."""
        ...
