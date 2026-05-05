"""Inference result repository interface (port)."""
from abc import ABC, abstractmethod
from typing import List, Optional

from elevator_pdm.domain.entities.inference_result import InferenceResult


class InferenceRepository(ABC):
    """Abstract interface for inference result operations."""

    @abstractmethod
    def save(self, result: InferenceResult) -> None:
        """Save an inference result."""
        ...

    @abstractmethod
    def find_by_elevator(
        self,
        elevator_id: str,
        from_ts: Optional[str] = None,
        to_ts: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[InferenceResult]:
        """Query inference results for an elevator with optional filters."""
        ...

    @abstractmethod
    def find_latest(self, elevator_id: str) -> Optional[InferenceResult]:
        """Get the most recent inference result for an elevator."""
        ...
