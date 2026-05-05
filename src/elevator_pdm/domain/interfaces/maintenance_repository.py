"""Maintenance repository interface (port)."""
from abc import ABC, abstractmethod
from typing import List, Optional

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
        status: Optional[str] = None,
    ) -> List[MaintenanceSchedule]:
        """Query maintenance records for an elevator with optional status filter."""
        ...

    @abstractmethod
    def update_status(self, maintenance_id: int, status: str, **kwargs) -> None:
        """Update maintenance status and optional fields (completed_at, technician)."""
        ...
