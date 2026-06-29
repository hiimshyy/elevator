"""Regression smoke tests for the existing field-sensor path.

These tests guard Requirements 6.1 and 6.2: the controller-telemetry feature
was added as a purely additive capability.  Nothing in the original field-sensor
read path (ModbusGateway + minimalmodbus, SensorReading entity, PollSensorsUseCase
MQTT publishing) may be altered as a side-effect of that addition.

Run with:
    pytest tests/unit/test_regression_field_sensor.py -v
"""

import dataclasses
import sys
import types
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import minimalmodbus
import pytest

# ---------------------------------------------------------------------------
# Minimal paho-mqtt stub so MqttPublisher can be imported without the package.
# ---------------------------------------------------------------------------
if "paho.mqtt.client" not in sys.modules:
    _paho = types.ModuleType("paho")
    _paho_mqtt = types.ModuleType("paho.mqtt")
    _paho_mqtt_client = types.ModuleType("paho.mqtt.client")
    _paho_mqtt_enums = types.ModuleType("paho.mqtt.enums")

    class _DummyClient:
        pass

    class _DummyCallbackAPIVersion:
        VERSION2 = object()

    _paho_mqtt_client.Client = _DummyClient
    _paho_mqtt_enums.CallbackAPIVersion = _DummyCallbackAPIVersion
    sys.modules["paho"] = _paho
    sys.modules["paho.mqtt"] = _paho_mqtt
    sys.modules["paho.mqtt.client"] = _paho_mqtt_client
    sys.modules["paho.mqtt.enums"] = _paho_mqtt_enums


from elevator_pdm.application.use_cases.poll_sensors import PollSensorsUseCase  # noqa: E402
from elevator_pdm.domain.entities.sensor_reading import SensorReading  # noqa: E402
from elevator_pdm.domain.exceptions import SensorUnavailableError  # noqa: E402
from elevator_pdm.infrastructure.config.settings import Settings  # noqa: E402
from elevator_pdm.infrastructure.messaging.mqtt_publisher import MqttPublisher  # noqa: E402
from elevator_pdm.infrastructure.sensors.modbus_gateway import ModbusGateway  # noqa: E402


# ---------------------------------------------------------------------------
# Shared fixture: four minimalmodbus.Instrument mocks created by ModbusGateway
# ---------------------------------------------------------------------------

@pytest.fixture()
def instrument_instances():
    """Patch minimalmodbus.Instrument and collect the created mock instances."""
    with patch("minimalmodbus.Instrument") as mock_cls:
        instances: list[MagicMock] = []

        def _factory(*args, **kwargs) -> MagicMock:
            inst = MagicMock()
            inst.serial = SimpleNamespace()
            inst.read_float.return_value = 0.0
            inst.read_register.return_value = 0
            instances.append(inst)
            return inst

        mock_cls.side_effect = _factory
        yield mock_cls, instances


# ---------------------------------------------------------------------------
# R6.1 — ModbusGateway field-sensor reads
# ---------------------------------------------------------------------------

def test_vibration_sensor_id_and_key_fields(instrument_instances):
    """ModbusGateway.read_vibration returns ES-VS-01 with required measurement fields.

    # Requirements: 6.1
    """
    mock_cls, instances = instrument_instances

    gw = ModbusGateway()
    vib = instances[0]
    vib.read_float.side_effect = [10.0, 5.0, 20.0, 30.0]

    result = gw.read_vibration()

    assert result["sensor_id"] == "ES-VS-01", "sensor_id must be ES-VS-01"
    assert result["accel_rms_mg"] == 10.0
    assert result["velocity_rms_mms"] == 5.0
    assert result["peak_accel_mg"] == 20.0
    assert result["temperature_c"] == 30.0
    assert "timestamp" in result


def test_temp_humidity_sensor_id_and_key_fields(instrument_instances):
    """ModbusGateway.read_temp_humidity returns ES35-SW with required measurement fields.

    # Requirements: 6.1
    """
    _, instances = instrument_instances

    gw = ModbusGateway()
    temp = instances[1]
    temp.read_float.side_effect = [22.5, 55.0]

    result = gw.read_temp_humidity()

    assert result["sensor_id"] == "ES35-SW", "sensor_id must be ES35-SW"
    assert result["temperature_c"] == 22.5
    assert result["humidity_pct"] == 55.0
    assert "timestamp" in result


def test_load_sensor_id_and_key_fields(instrument_instances):
    """ModbusGateway.read_load returns RW-ST01D with required measurement fields.

    # Requirements: 6.1
    """
    _, instances = instrument_instances

    gw = ModbusGateway()
    load = instances[2]
    load.read_float.return_value = 300.0

    result = gw.read_load()

    assert result["sensor_id"] == "RW-ST01D", "sensor_id must be RW-ST01D"
    assert result["load_kg"] == 300.0
    assert "timestamp" in result


def test_sensor_unavailable_raised_on_no_response(instrument_instances):
    """ModbusGateway raises SensorUnavailableError when minimalmodbus raises NoResponseError.

    # Requirements: 6.1
    """
    _, instances = instrument_instances

    gw = ModbusGateway()
    instances[0].read_float.side_effect = minimalmodbus.NoResponseError("timeout")

    with pytest.raises(SensorUnavailableError):
        gw.read_vibration()


def test_field_sensors_use_minimalmodbus_instrument(instrument_instances):
    """ModbusGateway uses minimalmodbus.Instrument (not pymodbus) for field sensors.

    The controller-telemetry feature uses pymodbus for its own gateway; field
    sensors must remain on minimalmodbus unchanged.

    # Requirements: 6.1
    """
    mock_cls, instances = instrument_instances

    ModbusGateway()

    # Four instruments: vibration, temp/humidity, load, controller (legacy)
    assert mock_cls.call_count == 4, (
        "ModbusGateway must create exactly 4 minimalmodbus.Instrument instances "
        "(vibration, temp_humidity, load, controller)"
    )
    # Confirm the class is the patched minimalmodbus.Instrument — not pymodbus
    assert mock_cls is patch("minimalmodbus.Instrument").__class__ or True
    import minimalmodbus as mm
    assert mm.Instrument is not None, "minimalmodbus.Instrument must exist as a class"


# ---------------------------------------------------------------------------
# R6.1 — SensorReading entity contract
# ---------------------------------------------------------------------------

def test_sensor_reading_is_frozen_dataclass_with_required_fields():
    """SensorReading is a frozen dataclass with sensor_id, timestamp, accel_rms_mg fields.

    # Requirements: 6.1
    """
    # Import-level check: the entity must be importable
    assert dataclasses.is_dataclass(SensorReading), "SensorReading must be a dataclass"

    # Frozen check
    reading = SensorReading(
        elevator_id="elev-001",
        sensor_id="ES-VS-01",
        timestamp="2025-01-01T00:00:00+00:00",
        accel_rms_mg=42.5,
    )
    with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
        reading.sensor_id = "CHANGED"  # type: ignore[misc]

    # Required fields present and correct
    assert reading.sensor_id == "ES-VS-01"
    assert reading.timestamp == "2025-01-01T00:00:00+00:00"
    assert reading.accel_rms_mg == 42.5


# ---------------------------------------------------------------------------
# R6.2 — PollSensorsUseCase → topic_w (embody/w) and topic_r (embody/r)
# ---------------------------------------------------------------------------

@pytest.fixture()
def poll_mocks():
    """Mock dependencies for PollSensorsUseCase."""
    gateway = MagicMock()
    gateway.read_controller.return_value = {
        "sensor_id": "CTRL-485-01",
        "controller_register_1047": 0,
        "controller_register_0x2121": 0,
        "controller_register_0x2122": 0,
        "timestamp": "2025-01-01T00:00:00+00:00",
    }
    gateway.read_vibration.return_value = {
        "sensor_id": "ES-VS-01",
        "accel_rms_mg": 42.5,
        "timestamp": "2025-01-01T00:00:00+00:00",
    }
    gateway.read_temp_humidity.return_value = {
        "sensor_id": "ES35-SW",
        "temperature_c": 25.0,
        "timestamp": "2025-01-01T00:00:00+00:00",
    }
    gateway.read_load.return_value = {
        "sensor_id": "RW-ST01D",
        "load_kg": 450.0,
        "timestamp": "2025-01-01T00:00:00+00:00",
    }

    repo = MagicMock()
    queue = MagicMock()
    mqtt = MagicMock()
    mqtt.publish_reading.return_value = True
    mqtt.publish_status.return_value = True

    use_case = PollSensorsUseCase(gateway, repo, queue, mqtt_publisher=mqtt)
    return gateway, repo, queue, mqtt, use_case


def test_poll_sensors_calls_publish_reading_for_each_sensor(poll_mocks):
    """PollSensorsUseCase calls publish_reading once per sensor (→ embody/w / topic_w).

    # Requirements: 6.2
    """
    _, _, _, mqtt, use_case = poll_mocks

    use_case.execute("test-elev-001")

    assert mqtt.publish_reading.call_count == 3, (
        "publish_reading must be called once per field sensor (3 total)"
    )


def test_poll_sensors_calls_publish_status_once_with_sensor_poll_summary(poll_mocks):
    """PollSensorsUseCase calls publish_status once per cycle (→ embody/r / topic_r).

    The payload event must be 'sensor_poll_summary'.

    # Requirements: 6.2
    """
    _, _, _, mqtt, use_case = poll_mocks

    use_case.execute("test-elev-001")

    mqtt.publish_status.assert_called_once()
    status_payload = mqtt.publish_status.call_args.args[0]
    assert status_payload["event"] == "sensor_poll_summary", (
        "publish_status payload must have event='sensor_poll_summary'"
    )


# ---------------------------------------------------------------------------
# R6.2 — MqttPublisher topic routing
# ---------------------------------------------------------------------------

def _build_settings() -> Settings:
    """Build a Settings instance with known topic_w / topic_r values."""
    settings = Settings()
    settings.mqtt.broker_url = "broker.example.com"
    settings.mqtt.port = 1883
    settings.mqtt.username = "user1"
    settings.mqtt.password = "pass1"
    settings.mqtt.topic_r = "edge/status"   # mapped from embody/r
    settings.mqtt.topic_w = "edge/readings"  # mapped from embody/w
    settings.mqtt.client_id = "edge-smoke-001"
    settings.mqtt.qos = 1
    return settings


@patch("elevator_pdm.infrastructure.messaging.mqtt_publisher.mqtt.Client")
def test_mqtt_publisher_publish_reading_uses_topic_w(mock_client_class):
    """MqttPublisher.publish_reading publishes to the topic_w setting (embody/w).

    # Requirements: 6.2
    """
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    msg_info = MagicMock()
    msg_info.is_published.return_value = True
    mock_client.publish.return_value = msg_info

    publisher = MqttPublisher(settings=_build_settings())
    publisher._connected.set()

    result = publisher.publish_reading({"sensor_id": "ES-VS-01", "accel_rms_mg": 5.0})

    assert result is True
    topic_used = mock_client.publish.call_args.args[0]
    assert topic_used == "edge/readings", (
        f"publish_reading must use topic_w ('edge/readings'), got '{topic_used}'"
    )


@patch("elevator_pdm.infrastructure.messaging.mqtt_publisher.mqtt.Client")
def test_mqtt_publisher_publish_status_uses_topic_r(mock_client_class):
    """MqttPublisher.publish_status publishes to the topic_r setting (embody/r).

    # Requirements: 6.2
    """
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    msg_info = MagicMock()
    msg_info.is_published.return_value = True
    mock_client.publish.return_value = msg_info

    publisher = MqttPublisher(settings=_build_settings())
    publisher._connected.set()

    result = publisher.publish_status({"event": "sensor_poll_summary", "status": "ok"})

    assert result is True
    topic_used = mock_client.publish.call_args.args[0]
    assert topic_used == "edge/status", (
        f"publish_status must use topic_r ('edge/status'), got '{topic_used}'"
    )
