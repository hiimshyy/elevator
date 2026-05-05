"""Redis queue adapter using LPUSH/BRPOP for sensor readings."""
import json
from typing import Optional

import redis


class RedisQueue:
    """Redis list-based queue for sensor readings (LPUSH/BRPOP)."""

    def __init__(self, redis_client: redis.Redis, queue_name: str = "sensor_queue") -> None:
        self._redis = redis_client
        self._queue_name = queue_name

    def enqueue(self, reading: dict) -> None:
        """Serialize and push a sensor reading to the Redis list."""
        payload = json.dumps(reading)
        self._redis.lpush(self._queue_name, payload)

    def dequeue(self, timeout: int = 5) -> Optional[dict]:
        """Block and pop a sensor reading from the Redis list.

        Returns:
            Deserialized reading dict, or None on timeout.
        """
        result = self._redis.brpop(self._queue_name, timeout=timeout)
        if result is None:
            return None
        _, payload = result
        return json.loads(payload)

    def length(self) -> int:
        """Get the current queue length."""
        return self._redis.llen(self._queue_name)
