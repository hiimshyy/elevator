import json
import logging
import threading
import time
from collections import deque
from typing import Any

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

from elevator_pdm.infrastructure.config.settings import Settings

logger = logging.getLogger(__name__)


class MqttPublisher:
    """MQTT Publisher for edge-to-cloud synchronization.

    Reads unsynchronized data and publishes it to a cloud broker.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or Settings()
        self._config = self._settings.mqtt
        self._validate_config()
        self._connected = threading.Event()
        self._connect_lock = threading.Lock()
        self._loop_started = False
        self._reconnect_failures = 0
        self._next_connect_not_before = 0.0
        self._pending_messages: deque[tuple[str, dict[str, Any]]] = deque(maxlen=200)
        self._client = mqtt.Client(
            callback_api_version=CallbackAPIVersion.VERSION2,
            client_id=self._config.client_id,
        )
        self._client.username_pw_set(self._config.username, self._config.password)
        self._client.reconnect_delay_set(min_delay=1, max_delay=30)
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect

    def _validate_config(self) -> None:
        if not self._config.broker_url.strip():
            raise ValueError("MQTT broker_url is required. Set ELEVATOR_MQTT__BROKER_URL.")
        if not self._config.username.strip():
            raise ValueError("MQTT username is required. Set ELEVATOR_MQTT__USERNAME.")
        if not self._config.password.strip():
            raise ValueError("MQTT password is required. Set ELEVATOR_MQTT__PASSWORD.")

    def _on_connect(
        self,
        client: mqtt.Client,
        userdata: Any,
        flags: Any,
        rc: Any,
        properties: Any = None,
    ) -> None:
        # rc.value for Paho MQTT v2 is 0 on success
        if hasattr(rc, "value") and rc.value == 0 or rc == 0:
            self._connected.set()
            self._reconnect_failures = 0
            self._next_connect_not_before = 0.0
            logger.info(
                "Connected to MQTT Broker at %s:%s",
                self._config.broker_url,
                self._config.port,
            )
        else:
            self._connected.clear()
            logger.error("Failed to connect to MQTT Broker, return code %s", rc)

    def _on_disconnect(
        self,
        client: mqtt.Client,
        userdata: Any,
        disconnect_flags: Any,
        rc: Any,
        properties: Any = None,
    ) -> None:
        self._connected.clear()
        if rc != 0:
            self._reconnect_failures += 1
            self._next_connect_not_before = time.monotonic() + self._reconnect_delay_s()
        logger.warning("Disconnected from MQTT Broker with return code %s", rc)

    def connect(self, timeout_s: float = 5.0) -> bool:
        """Connects to the MQTT broker and starts the background network loop."""
        now = time.monotonic()
        if now < self._next_connect_not_before:
            retry_in_s = self._next_connect_not_before - now
            logger.warning(
                "Skipping MQTT reconnect attempt for %.1fs because broker is in cooldown",
                retry_in_s,
            )
            return False

        if self._connected.is_set():
            return True

        if not self._connect_lock.acquire(blocking=False):
            return self._connected.wait(timeout=timeout_s)

        try:
            if not self._loop_started:
                host = self._config.broker_url.strip()
                if "://" in host:
                    host = host.split("://")[-1]
                self._client.connect(host, self._config.port, keepalive=60)
                self._client.loop_start()
                self._loop_started = True
            elif not self._connected.is_set():
                self._client.reconnect()

            if not self._connected.wait(timeout=timeout_s):
                logger.error(
                    "Timed out waiting for MQTT connection to %s:%s",
                    self._config.broker_url,
                    self._config.port,
                )
                self._reconnect_failures += 1
                self._next_connect_not_before = time.monotonic() + self._reconnect_delay_s()
                return False
            return True
        except Exception as e:
            logger.error("Error connecting to MQTT Broker: %s", e)
            self._connected.clear()
            self._reconnect_failures += 1
            self._next_connect_not_before = time.monotonic() + self._reconnect_delay_s()
            return False
        finally:
            self._connect_lock.release()

    def disconnect(self) -> None:
        """Stops the network loop and disconnects from the broker."""
        if self._loop_started:
            self._client.loop_stop()
            self._loop_started = False
        self._connected.clear()
        self._next_connect_not_before = 0.0
        self._client.disconnect()

    def publish_reading(self, payload: dict[str, Any]) -> bool:
        """Publishes sensor reading data to the 'topic_w' topic.
        Used for writing data to the cloud.
        """
        return self._publish(self._config.topic_w, payload)

    def publish_status(self, payload: dict[str, Any]) -> bool:
        """Publishes general status or alerts to the 'topic_r' topic.
        Used for reporting edge status.
        """
        return self._publish(self._config.topic_r, payload)

    def publish_controller_snapshot(self, payload: dict[str, Any]) -> bool:
        """Publishes a flat controller telemetry snapshot to the elevator topic.

        The topic is sourced from ``Settings.controller_telemetry.topic_elevator``
        at QoS 1.  Returns ``False`` on failure without raising; failures are
        logged and treated as non-fatal.
        """
        topic = self._settings.controller_telemetry.topic_elevator
        return self._publish(topic, payload, qos=1)

    def _publish(self, topic: str, payload: dict[str, Any], *, qos: int | None = None) -> bool:
        """Internal generic publish method.

        Args:
            topic:   MQTT topic to publish to.
            payload: JSON-serialisable dict to send as the message body.
            qos:     QoS level override.  When ``None``, falls back to the
                     value configured in ``Settings.mqtt.qos``.
        """
        effective_qos = qos if qos is not None else self._config.qos
        try:
            if not self._ensure_connected():
                self._enqueue_pending(topic, payload)
                logger.error("MQTT publish skipped because client is not connected")
                return False

            self._flush_pending()
            msg_str = json.dumps(payload)
            # paho-mqtt version 2.0+ publish() returns MQTTMessageInfo
            result = self._client.publish(topic, msg_str, qos=effective_qos)
            result.wait_for_publish(timeout=5.0)

            if result.is_published():
                logger.debug("Successfully published message to %s", topic)
                return True
            self._enqueue_pending(topic, payload)
            logger.error("Failed to publish message to %s", topic)
            return False
        except Exception as e:
            self._enqueue_pending(topic, payload)
            logger.error("Exception during MQTT publish: %s", e)
            return False

    def _ensure_connected(self) -> bool:
        if self._connected.is_set():
            return True
        return self.connect(timeout_s=5.0)

    def _enqueue_pending(self, topic: str, payload: dict[str, Any]) -> None:
        queue_was_full = len(self._pending_messages) == self._pending_messages.maxlen
        self._pending_messages.append((topic, payload))
        if queue_was_full:
            logger.warning(
                "MQTT pending queue reached capacity; oldest message was dropped for client %s",
                self._config.client_id,
            )

    def _flush_pending(self) -> None:
        if not self._pending_messages or not self._connected.is_set():
            return

        pending_count = len(self._pending_messages)
        logger.info("Flushing %s queued MQTT message(s)", pending_count)
        for _ in range(pending_count):
            topic, payload = self._pending_messages.popleft()
            if not self._publish_immediately(topic, payload):
                self._pending_messages.appendleft((topic, payload))
                break

    def _publish_immediately(self, topic: str, payload: dict[str, Any]) -> bool:
        msg_str = json.dumps(payload)
        result = self._client.publish(topic, msg_str, qos=self._config.qos)
        result.wait_for_publish(timeout=5.0)
        if result.is_published():
            logger.debug("Successfully published message to %s", topic)
            return True
        logger.error("Failed to publish message to %s", topic)
        return False

    def _reconnect_delay_s(self) -> float:
        if self._reconnect_failures <= 0:
            return 0.0
        return float(min(2 ** (self._reconnect_failures - 1), 30))
