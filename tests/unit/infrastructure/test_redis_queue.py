"""Tests for RedisQueue implementation using fakeredis."""
import json
import pytest
from fakeredis import FakeRedis

from elevator_pdm.infrastructure.messaging.redis_queue import RedisQueue
from elevator_pdm.domain.entities.sensor_reading import SensorReading


@pytest.fixture
def queue():
    """Create a RedisQueue with a fake Redis client."""
    redis_client = FakeRedis()
    return RedisQueue(redis_client, "test_queue"), redis_client


def test_enqueue_serializes_to_json_and_pushes(queue):
    queue, redis_client = queue
    reading = {
        "elevator_id": "test-elev-001",
        "sensor_id": "ES-VS-01",
        "timestamp": "2025-01-01T00:00:00+00:00",
        "accel_rms_mg": 42.5,
    }
    queue.enqueue(reading)

    # Verify raw data in Redis
    raw = redis_client.lindex("test_queue", 0)
    assert raw is not None
    deserialized = json.loads(raw)
    assert deserialized["elevator_id"] == "test-elev-001"
    assert deserialized["accel_rms_mg"] == 42.5


def test_dequeue_returns_deserialized_reading(queue):
    queue, redis_client = queue
    reading = {
        "elevator_id": "test-elev-001",
        "sensor_id": "ES-VS-01",
        "timestamp": "2025-01-01T00:00:00+00:00",
        "accel_rms_mg": 42.5,
    }
    queue.enqueue(reading)

    result = queue.dequeue(timeout=1)
    assert result is not None
    assert result["elevator_id"] == "test-elev-001"
    assert result["sensor_id"] == "ES-VS-01"
    assert result["accel_rms_mg"] == 42.5


def test_dequeue_blocks_and_returns_none_on_timeout(queue):
    queue, redis_client = queue
    result = queue.dequeue(timeout=1)
    assert result is None


def test_length_returns_queue_size(queue):
    queue, redis_client = queue
    assert queue.length() == 0

    reading = {"elevator_id": "test-elev-001", "sensor_id": "ES-VS-01"}
    queue.enqueue(reading)
    queue.enqueue(reading)

    assert queue.length() == 2


def test_fifo_order_preserved(queue):
    queue, redis_client = queue

    for i in range(3):
        reading = {"index": i, "sensor_id": "ES-VS-01"}
        queue.enqueue(reading)

    for i in range(3):
        result = queue.dequeue(timeout=1)
        assert result["index"] == i

    # Queue should be empty now
    assert queue.length() == 0


def test_enqueue_domain_entity_dict(queue):
    queue, redis_client = queue
    # Test with domain entity converted to dict
    reading = SensorReading(
        elevator_id="test-elev-001",
        sensor_id="ES-VS-01",
        timestamp="2025-01-01T00:00:00+00:00",
        accel_rms_mg=42.5,
    )
    reading_dict = {
        "elevator_id": reading.elevator_id,
        "sensor_id": reading.sensor_id,
        "timestamp": reading.timestamp,
        "accel_rms_mg": reading.accel_rms_mg,
    }
    queue.enqueue(reading_dict)

    result = queue.dequeue(timeout=1)
    assert result["elevator_id"] == "test-elev-001"
    assert result["accel_rms_mg"] == 42.5
