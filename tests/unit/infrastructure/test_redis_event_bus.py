"""Tests for RedisEventBus implementation using fakeredis."""
import json
import pytest
from fakeredis import FakeRedis

from elevator_pdm.infrastructure.messaging.redis_event_bus import RedisEventBus


@pytest.fixture
def event_bus():
    """Create a RedisEventBus with a fake Redis client."""
    redis_client = FakeRedis()
    return RedisEventBus(redis_client), redis_client


def test_publish_and_subscribe_delivers_events(event_bus):
    bus, redis_client = event_bus
    received_events = []

    def handler(payload):
        received_events.append(payload)

    bus.subscribe("anomaly_detected", handler)
    bus.publish("anomaly_detected", {"elevator_id": "test-001", "status": "WARNING"})

    # Give time for the subscriber thread to process
    import time
    time.sleep(0.5)

    assert len(received_events) == 1
    assert received_events[0]["elevator_id"] == "test-001"
    assert received_events[0]["status"] == "WARNING"


def test_multiple_subscribers_receive_event(event_bus):
    bus, redis_client = event_bus
    received1 = []
    received2 = []

    def handler1(payload):
        received1.append(payload)

    def handler2(payload):
        received2.append(payload)

    bus.subscribe("anomaly_detected", handler1)
    bus.subscribe("anomaly_detected", handler2)
    bus.publish("anomaly_detected", {"test": "data"})

    import time
    time.sleep(0.5)

    assert len(received1) == 1
    assert len(received2) == 1


def test_filter_by_event_type(event_bus):
    bus, redis_client = event_bus
    anomaly_events = []
    alert_events = []

    def anomaly_handler(payload):
        anomaly_events.append(payload)

    def alert_handler(payload):
        alert_events.append(payload)

    bus.subscribe("anomaly_detected", anomaly_handler)
    bus.subscribe("alert_raised", alert_handler)

    bus.publish("anomaly_detected", {"type": "anomaly"})
    bus.publish("alert_raised", {"type": "alert"})

    import time
    time.sleep(0.5)

    assert len(anomaly_events) == 1
    assert len(alert_events) == 1
    assert anomaly_events[0]["type"] == "anomaly"
    assert alert_events[0]["type"] == "alert"


def test_unsubscribe_stops_receiving(event_bus):
    bus, redis_client = event_bus
    received = []

    def handler(payload):
        received.append(payload)

    bus.subscribe("anomaly_detected", handler)
    bus.publish("anomaly_detected", {"test": 1})

    import time
    time.sleep(0.3)

    assert len(received) == 1

    # Unsubscribe and publish again
    bus.unsubscribe("anomaly_detected", handler)
    bus.publish("anomaly_detected", {"test": 2})

    time.sleep(0.3)

    # Should still be 1 (new event not received)
    assert len(received) == 1


def test_publish_json_serialization(event_bus):
    bus, redis_client = event_bus
    received = []

    def handler(payload):
        received.append(payload)

    bus.subscribe("test_event", handler)

    payload = {
        "elevator_id": "test-001",
        "confidence": 0.95,
        "status": "CRITICAL",
        "nested": {"key": "value"},
    }
    bus.publish("test_event", payload)

    import time
    time.sleep(0.3)

    assert len(received) == 1
    assert received[0]["confidence"] == 0.95
    assert received[0]["nested"]["key"] == "value"
