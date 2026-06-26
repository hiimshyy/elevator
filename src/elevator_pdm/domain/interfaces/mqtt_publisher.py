"""MQTT publisher port for application-layer publishing."""
from typing import Any, Protocol


class MqttPublisher(Protocol):
    """Application-facing contract for publishing MQTT payloads."""

    def publish_reading(self, payload: dict[str, Any]) -> bool: ...

    def publish_status(self, payload: dict[str, Any]) -> bool: ...

    def publish_controller_snapshot(self, payload: dict[str, Any]) -> bool: ...
