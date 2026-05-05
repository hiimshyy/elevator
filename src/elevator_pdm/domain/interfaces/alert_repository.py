"""Alert repository interface (port)."""
from abc import ABC, abstractmethod
from typing import List, Optional

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
        severity: Optional[str] = None,
        acknowledged: Optional[bool] = None,
    ) -> List[Alert]:
        """Query alerts for an elevator with optional filters."""
        ...

    @abstractmethod
    def acknowledge(self, alert_id: int, acknowledged_by: str) -> None:
        """Mark an alert as acknowledged."""
        ...
