"""Tests for ModbusGateway sensor implementation."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import minimalmodbus
import pytest
import serial

from elevator_pdm.domain.exceptions import SensorUnavailableError
from elevator_pdm.infrastructure.sensors.modbus_gateway import ModbusGateway


@pytest.fixture
def instrument_instances():
    with patch("minimalmodbus.Instrument") as mock_cls:
        instances: list[MagicMock] = []

        def build_instance(*args, **kwargs):
            instrument = MagicMock()
            instrument.serial = SimpleNamespace()
            instrument.read_float.return_value = 0.0
            instrument.read_register.return_value = 0
            instances.append(instrument)
            return instrument

        mock_cls.side_effect = build_instance
        yield mock_cls, instances


def test_read_vibration_calls_correct_registers(instrument_instances):
    mock_cls, instances = instrument_instances

    gw = ModbusGateway()
    vib = instances[0]
    vib.read_float.side_effect = [42.5, 12.3, 98.0, 25.0]

    result = gw.read_vibration()

    assert result["sensor_id"] == "ES-VS-01"
    assert result["accel_rms_mg"] == 42.5
    assert result["velocity_rms_mms"] == 12.3
    assert result["peak_accel_mg"] == 98.0
    assert result["temperature_c"] == 25.0
    assert "timestamp" in result
    assert mock_cls.call_count == 4


def test_read_temp_humidity_calls_correct_registers(instrument_instances):
    _, instances = instrument_instances

    gw = ModbusGateway()
    temp = instances[1]
    temp.read_float.side_effect = [23.5, 60.0]

    result = gw.read_temp_humidity()

    assert result["sensor_id"] == "ES35-SW"
    assert result["temperature_c"] == 23.5
    assert result["humidity_pct"] == 60.0
    assert "timestamp" in result


def test_read_load_calls_correct_registers(instrument_instances):
    _, instances = instrument_instances

    gw = ModbusGateway()
    load = instances[2]
    load.read_float.return_value = 450.0

    result = gw.read_load()

    assert result["sensor_id"] == "RW-ST01D"
    assert result["load_kg"] == 450.0
    assert "timestamp" in result


def test_read_controller_reads_requested_registers(instrument_instances):
    _, instances = instrument_instances

    gw = ModbusGateway()
    controller = instances[3]
    controller.read_register.side_effect = [100, 200, 201]

    result = gw.read_controller()

    assert result["sensor_id"] == "CTRL-485-01"
    assert result["controller_reg_current_floor"] == 100
    assert result["controller_reg_current"] == 200
    assert result["controller_reg_voltage"] == 201
    controller.read_register.assert_any_call(0x2111, functioncode=3, signed=False)
    controller.read_register.assert_any_call(0x2121, functioncode=3, signed=False)
    controller.read_register.assert_any_call(0x2122, functioncode=3, signed=False)


def test_raises_sensor_unavailable_on_modbus_error(instrument_instances):
    _, instances = instrument_instances

    gw = ModbusGateway()
    vib = instances[0]
    vib.read_float.side_effect = minimalmodbus.NoResponseError("Timeout")

    with pytest.raises(SensorUnavailableError):
        gw.read_vibration()


def test_creates_four_instruments_with_expected_serial_settings(instrument_instances):
    mock_cls, instances = instrument_instances

    ModbusGateway()

    assert mock_cls.call_count == 4
    for instrument in instances:
        assert instrument.serial.baudrate == 19200
        assert instrument.serial.timeout == 1.0
        assert instrument.serial.bytesize == serial.EIGHTBITS
        assert instrument.serial.parity == serial.PARITY_EVEN
        assert instrument.serial.stopbits == serial.STOPBITS_ONE


def test_can_create_controller_only_gateway(instrument_instances):
    mock_cls, instances = instrument_instances

    gw = ModbusGateway(enabled_sensors={"controller"})
    controller = instances[0]
    controller.read_register.side_effect = [100, 200, 201]

    result = gw.read_controller()

    assert mock_cls.call_count == 1
    assert result["controller_reg_current_floor"] == 100
    assert result["controller_reg_current"] == 200
    assert result["controller_reg_voltage"] == 201
