"""Event bus interface (port) for domain events."""
from abc import ABC, abstractmethod
from typing import Callable, Any


class EventBus(ABC):
    """Abstract interface for publishing/subscribing domain events."""

    @abstractmethod
    def publish(self, event_type: str, payload: dict) -> None:
        """Publish a domain event."""
        ...

    @abstractmethod
    def subscribe(self, event_type: str, handler: Callable[[dict], None]) -> None:
        """Subscribe to domain events of a given type."""
        ...

    @abstractmethod
    def unsubscribe(self, event_type: str, handler: Callable[[dict], None]) -> None:
        """Unsubscribe a handler from domain events."""
        ...
