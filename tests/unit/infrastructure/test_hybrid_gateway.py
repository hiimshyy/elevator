"""Tests for HybridGateway."""

from unittest.mock import MagicMock, patch

from elevator_pdm.infrastructure.sensors.hybrid_gateway import HybridGateway


@patch("elevator_pdm.infrastructure.sensors.hybrid_gateway.ModbusGateway")
@patch("elevator_pdm.infrastructure.sensors.hybrid_gateway.MockGateway")
def test_hybrid_gateway_uses_mock_for_external_sensors(
    mock_gateway_class,
    modbus_gateway_class,
):
    mock_gateway = MagicMock()
    mock_gateway.read_vibration.return_value = {"sensor_id": "ES-VS-01"}
    mock_gateway.read_temp_humidity.return_value = {"sensor_id": "ES35-SW"}
    mock_gateway.read_load.return_value = {"sensor_id": "RW-ST01D"}
    mock_gateway_class.return_value = mock_gateway

    modbus_gateway = MagicMock()
    modbus_gateway_class.return_value = modbus_gateway

    gateway = HybridGateway()

    assert gateway.read_vibration()["sensor_id"] == "ES-VS-01"
    assert gateway.read_temp_humidity()["sensor_id"] == "ES35-SW"
    assert gateway.read_load()["sensor_id"] == "RW-ST01D"
    modbus_gateway.read_controller.assert_not_called()


@patch("elevator_pdm.infrastructure.sensors.hybrid_gateway.ModbusGateway")
@patch("elevator_pdm.infrastructure.sensors.hybrid_gateway.MockGateway")
def test_hybrid_gateway_uses_modbus_for_controller(
    mock_gateway_class,
    modbus_gateway_class,
):
    mock_gateway_class.return_value = MagicMock()

    modbus_gateway = MagicMock()
    modbus_gateway.read_controller.return_value = {
        "sensor_id": "CTRL-485-01",
        "controller_register_1047": 100,
        "controller_register_0x2121": 200,
        "controller_register_0x2122": 201,
    }
    modbus_gateway_class.return_value = modbus_gateway

    gateway = HybridGateway()
    result = gateway.read_controller()

    modbus_gateway_class.assert_called_once_with(
        settings=gateway._settings,
        enabled_sensors={"controller"},
    )
    assert result["sensor_id"] == "CTRL-485-01"
    assert result["controller_register_1047"] == 100
    assert result["controller_register_0x2121"] == 200
    assert result["controller_register_0x2122"] == 201
