"""Redis event bus adapter using Pub/Sub for domain events."""
import json
from typing import Callable, Any, Dict
import threading

import redis


class RedisEventBus:
    """Redis Pub/Sub implementation of EventBus."""

    def __init__(self, redis_client: redis.Redis) -> None:
        self._redis = redis_client
        self._subscribers: Dict[str, list[Callable]] = {}
        self._lock = threading.Lock()
        self._pubsub = None
        self._subscriber_thread = None

    def publish(self, event_type: str, payload: dict) -> None:
        """Publish a domain event to Redis channel."""
        message = json.dumps(payload)
        self._redis.publish(event_type, message)

    def subscribe(self, event_type: str, handler: Callable[[dict], None]) -> None:
        """Subscribe to domain events of a given type."""
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(handler)

        # Start subscribing in background if not already running
        if self._subscriber_thread is None or not self._subscriber_thread.is_alive():
            self._start_subscriber()
        else:
            # Dynamically subscribe to the new channel
            if self._pubsub is not None:
                self._pubsub.subscribe(event_type)

    def unsubscribe(self, event_type: str, handler: Callable[[dict], None]) -> None:
        """Unsubscribe a handler from domain events."""
        with self._lock:
            if event_type in self._subscribers:
                self._subscribers[event_type] = [
                    h for h in self._subscribers[event_type] if h != handler
                ]

    def _start_subscriber(self) -> None:
        """Start a background thread to listen for Pub/Sub messages."""
        self._pubsub = self._redis.pubsub()
        with self._lock:
            for event_type in self._subscribers:
                self._pubsub.subscribe(event_type)

        def _listen():
            for message in self._pubsub.listen():
                if message["type"] == "message":
                    channel = message["channel"]
                    if isinstance(channel, bytes):
                        channel = channel.decode("utf-8")
                    try:
                        payload = json.loads(message["data"])
                    except (json.JSONDecodeError, TypeError):
                        continue

                    with self._lock:
                        handlers = self._subscribers.get(channel, [])

                    for handler in handlers:
                        try:
                            handler(payload)
                        except Exception:
                            pass  # Don't let handler exceptions crash the listener

        self._subscriber_thread = threading.Thread(target=_listen, daemon=True)
        self._subscriber_thread.start()
