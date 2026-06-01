"""Alert repository interface (port)."""
from abc import ABC, abstractmethod

from elevator_pdm.domain.entities.alert import Alert


class AlertRepository(ABC):
    """Abstract interface for alert operations."""

    @abstractmethod
    def save(self, alert: Alert) -> None:
        """Save an alert."""
        ...

    @abstractmethod
    def find_by_elevator(
        self,
        elevator_id: str,
        severity: str | None = None,
        acknowledged: bool | None = None,
    ) -> list[Alert]:
        """Query alerts for an elevator with optional filters."""
        ...

    @abstractmethod
    def find_all(
        self,
        severity: str | None = None,
        acknowledged: bool | None = None,
    ) -> list[Alert]:
        """Query alerts across all elevators with optional filters."""
        ...

    @abstractmethod
    def get_by_id(self, alert_id: int) -> Alert | None:
        """Get a single alert by its database ID."""
        ...

    @abstractmethod
    def acknowledge(self, alert_id: int, acknowledged_by: str) -> None:
        """Mark an alert as acknowledged."""
        ...
