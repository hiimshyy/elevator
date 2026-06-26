"""Controller snapshot repository interface (port)."""
from abc import ABC, abstractmethod

from elevator_pdm.domain.entities.controller_snapshot import ControllerSnapshot


class ControllerSnapshotRepository(ABC):
    """Abstract interface for persisting and querying controller snapshots."""

    @abstractmethod
    def save(self, snapshot: ControllerSnapshot) -> None:
        """Persist a single controller snapshot."""
        ...

    @abstractmethod
    def find_by_elevator(
        self,
        elevator_id: str,
        from_ts: str | None = None,
        to_ts: str | None = None,
        limit: int = 500,
    ) -> list[ControllerSnapshot]:
        """Query controller snapshots for an elevator with optional time filters."""
        ...

    @abstractmethod
    def find_latest(self, elevator_id: str) -> ControllerSnapshot | None:
        """Get the most recent controller snapshot for an elevator."""
        ...
