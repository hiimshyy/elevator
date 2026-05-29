"""Tests for MQTT publisher adapter."""

import sys
import types
from unittest.mock import MagicMock, patch

# Provide a minimal paho-mqtt stub when the dependency is unavailable
if "paho.mqtt.client" not in sys.modules:
    paho_module = types.ModuleType("paho")
    paho_mqtt_module = types.ModuleType("paho.mqtt")
    paho_mqtt_client_module = types.ModuleType("paho.mqtt.client")
    paho_mqtt_enums_module = types.ModuleType("paho.mqtt.enums")

    class _DummyClient:
        pass

    class _DummyCallbackAPIVersion:
        VERSION2 = object()

    paho_mqtt_client_module.Client = _DummyClient
    paho_mqtt_enums_module.CallbackAPIVersion = _DummyCallbackAPIVersion

    sys.modules["paho"] = paho_module
    sys.modules["paho.mqtt"] = paho_mqtt_module
    sys.modules["paho.mqtt.client"] = paho_mqtt_client_module
    sys.modules["paho.mqtt.enums"] = paho_mqtt_enums_module

from elevator_pdm.infrastructure.config.settings import Settings
from elevator_pdm.infrastructure.messaging.mqtt_publisher import MqttPublisher


def _build_settings() -> Settings:
    settings = Settings()
    settings.mqtt.broker_url = "broker.example.com"
    settings.mqtt.port = 1883
    settings.mqtt.username = "user1"
    settings.mqtt.password = "pass1"
    settings.mqtt.topic_r = "edge/status"
    settings.mqtt.topic_w = "edge/readings"
    settings.mqtt.client_id = "edge-001"
    settings.mqtt.qos = 1
    return settings


@patch("elevator_pdm.infrastructure.messaging.mqtt_publisher.mqtt.Client")
def test_init_sets_credentials_and_callbacks(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client

    settings = _build_settings()
    publisher = MqttPublisher(settings=settings)

    assert publisher is not None
    mock_client.username_pw_set.assert_called_once_with("user1", "pass1")
    assert mock_client.on_connect is not None
    assert mock_client.on_disconnect is not None


@patch("elevator_pdm.infrastructure.messaging.mqtt_publisher.mqtt.Client")
def test_connect_calls_client_connect_and_loop_start(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client

    publisher = MqttPublisher(settings=_build_settings())
    publisher.connect()

    mock_client.connect.assert_called_once_with("broker.example.com", 1883, keepalive=60)
    mock_client.loop_start.assert_called_once()


@patch("elevator_pdm.infrastructure.messaging.mqtt_publisher.mqtt.Client")
def test_disconnect_calls_loop_stop_and_disconnect(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client

    publisher = MqttPublisher(settings=_build_settings())
    publisher.disconnect()

    mock_client.loop_stop.assert_called_once()
    mock_client.disconnect.assert_called_once()


@patch("elevator_pdm.infrastructure.messaging.mqtt_publisher.mqtt.Client")
def test_publish_reading_uses_topic_w_and_returns_true_on_success(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client

    message_info = MagicMock()
    message_info.is_published.return_value = True
    mock_client.publish.return_value = message_info

    publisher = MqttPublisher(settings=_build_settings())
    payload = {"elevator_id": "elev-001", "load_kg": 350.5}

    result = publisher.publish_reading(payload)

    assert result is True
    mock_client.publish.assert_called_once_with(
        "edge/readings",
        '{"elevator_id": "elev-001", "load_kg": 350.5}',
        qos=1,
    )
    message_info.wait_for_publish.assert_called_once_with(timeout=5.0)


@patch("elevator_pdm.infrastructure.messaging.mqtt_publisher.mqtt.Client")
def test_publish_status_uses_topic_r(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client

    message_info = MagicMock()
    message_info.is_published.return_value = True
    mock_client.publish.return_value = message_info

    publisher = MqttPublisher(settings=_build_settings())
    result = publisher.publish_status({"status": "ok"})

    assert result is True
    mock_client.publish.assert_called_once_with("edge/status", '{"status": "ok"}', qos=1)


@patch("elevator_pdm.infrastructure.messaging.mqtt_publisher.mqtt.Client")
def test_publish_returns_false_when_not_published(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client

    message_info = MagicMock()
    message_info.is_published.return_value = False
    mock_client.publish.return_value = message_info

    publisher = MqttPublisher(settings=_build_settings())
    result = publisher.publish_reading({"x": 1})

    assert result is False


@patch("elevator_pdm.infrastructure.messaging.mqtt_publisher.mqtt.Client")
def test_publish_returns_false_on_exception(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    mock_client.publish.side_effect = RuntimeError("publish failed")

    publisher = MqttPublisher(settings=_build_settings())
    result = publisher.publish_reading({"x": 1})

    assert result is False
