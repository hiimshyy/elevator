import json
import logging
from typing import Any, Dict

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
        self._client = mqtt.Client(
            callback_api_version=CallbackAPIVersion.VERSION2, 
            client_id=self._config.client_id
        )
        
        if self._config.username and self._config.password:
            self._client.username_pw_set(self._config.username, self._config.password)
            
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        
    def _on_connect(self, client: mqtt.Client, userdata: Any, flags: Any, rc: Any, properties: Any = None) -> None:
        # rc.value for Paho MQTT v2 is 0 on success
        if hasattr(rc, "value") and rc.value == 0 or rc == 0:
            logger.info(f"Connected to MQTT Broker at {self._config.broker_url}:{self._config.port}")
        else:
            logger.error(f"Failed to connect to MQTT Broker, return code {rc}")

    def _on_disconnect(self, client: mqtt.Client, userdata: Any, disconnect_flags: Any, rc: Any, properties: Any = None) -> None:
        logger.warning(f"Disconnected from MQTT Broker with return code {rc}")

    def connect(self) -> None:
        """Connects to the MQTT broker and starts the background network loop."""
        try:
            self._client.connect(self._config.broker_url, self._config.port, keepalive=60)
            self._client.loop_start()
        except Exception as e:
            logger.error(f"Error connecting to MQTT Broker: {e}")

    def disconnect(self) -> None:
        """Stops the network loop and disconnects from the broker."""
        self._client.loop_stop()
        self._client.disconnect()

    def publish_reading(self, payload: Dict[str, Any]) -> bool:
        """Publishes sensor reading data to the 'topic_w' topic.
        Used for writing data to the cloud.
        """
        return self._publish(self._config.topic_w, payload)
        
    def publish_status(self, payload: Dict[str, Any]) -> bool:
        """Publishes general status or alerts to the 'topic_r' topic.
        Used for reporting edge status.
        """
        return self._publish(self._config.topic_r, payload)
        
    def _publish(self, topic: str, payload: Dict[str, Any]) -> bool:
        """Internal generic publish method."""
        try:
            msg_str = json.dumps(payload)
            # paho-mqtt version 2.0+ publish() returns MQTTMessageInfo
            result = self._client.publish(topic, msg_str, qos=self._config.qos)
            result.wait_for_publish(timeout=5.0)
            
            if result.is_published():
                logger.debug(f"Successfully published message to {topic}")
                return True
            else:
                logger.error(f"Failed to publish message to {topic}")
                return False
        except Exception as e:
            logger.error(f"Exception during MQTT publish: {e}")
            return False
