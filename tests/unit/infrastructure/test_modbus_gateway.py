"""Tests for ModbusGateway sensor implementation."""
import minimalmodbus
from unittest.mock import MagicMock, patch

import pytest

from elevator_pdm.infrastructure.sensors.modbus_gateway import ModbusGateway
from elevator_pdm.domain.exceptions import SensorUnavailableError


@pytest.fixture
def mock_instrument():
    with patch("minimalmodbus.Instrument") as mock:
        instance = MagicMock()
        instance.read_float.return_value = 0.0
        mock.return_value = instance
        yield mock, instance


def test_read_vibration_calls_correct_registers(mock_instrument):
    mock_cls, instance = mock_instrument
    instance.read_float.side_effect = [42.5, 12.3, 98.0, 25.0]

    gw = ModbusGateway()
    result = gw.read_vibration()

    assert result["sensor_id"] == "ES-VS-01"
    assert result["accel_rms_mg"] == 42.5
    assert result["velocity_rms_mms"] == 12.3
    assert result["peak_accel_mg"] == 98.0
    assert result["temperature_c"] == 25.0
    assert "timestamp" in result


def test_read_temp_humidity_calls_correct_registers(mock_instrument):
    mock_cls, instance = mock_instrument
    instance.read_float.side_effect = [23.5, 60.0]

    gw = ModbusGateway()
    result = gw.read_temp_humidity()

    assert result["sensor_id"] == "ES35-SW"
    assert result["temperature_c"] == 23.5
    assert result["humidity_pct"] == 60.0
    assert "timestamp" in result


def test_read_load_calls_correct_registers(mock_instrument):
    mock_cls, instance = mock_instrument
    instance.read_float.return_value = 450.0

    gw = ModbusGateway()
    result = gw.read_load()

    assert result["sensor_id"] == "RW-ST01D"
    assert result["load_kg"] == 450.0
    assert "timestamp" in result


def test_raises_sensor_unavailable_on_modbus_error(mock_instrument):
    mock_cls, instance = mock_instrument
    instance.read_float.side_effect = minimalmodbus.NoResponseError("Timeout")

    gw = ModbusGateway()
    with pytest.raises(SensorUnavailableError):
        gw.read_vibration()


def test_creates_three_instruments_with_correct_slave_ids(mock_instrument):
    mock_cls, instance = mock_instrument
    gw = ModbusGateway()
    assert mock_cls.call_count == 3
