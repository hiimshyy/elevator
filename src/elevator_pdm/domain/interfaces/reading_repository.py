"""Reading repository interface (port)."""
from abc import ABC, abstractmethod
from typing import List, Optional

from elevator_pdm.domain.entities.sensor_reading import SensorReading


class ReadingRepository(ABC):
    """Abstract interface for persisting and querying sensor readings."""

    @abstractmethod
    def save(self, reading: SensorReading) -> None:
        """Persist a single sensor reading."""
        ...

    @abstractmethod
    def find_by_elevator(
        self,
        elevator_id: str,
        from_ts: Optional[str] = None,
        to_ts: Optional[str] = None,
        sensor_id: Optional[str] = None,
        limit: int = 500,
    ) -> List[SensorReading]:
        """Query readings for an elevator with optional filters."""
        ...

    @abstractmethod
    def find_latest(self, elevator_id: str) -> Optional[SensorReading]:
        """Get the most recent reading for an elevator."""
        ...

    @abstractmethod
    def find_unsynced(self, limit: int = 1000) -> List[SensorReading]:
        """Get readings not yet synced to cloud."""
        ...

    @abstractmethod
    def mark_synced(self, reading_ids: List[int]) -> None:
        """Mark readings as synced to cloud."""
        ...
