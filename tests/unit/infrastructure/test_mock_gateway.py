"""Tests for MockGateway sensor implementation."""
import pytest
from src.elevator_pdm.infrastructure.sensors.mock_gateway import MockGateway


def test_read_vibration_returns_valid_dict():
    gw = MockGateway(seed=42)
    result = gw.read_vibration()
    assert result["sensor_id"] == "ES-VS-01"
    assert "accel_rms_mg" in result
    assert "velocity_rms_mms" in result
    assert "peak_accel_mg" in result
    assert "temperature_c" in result
    assert "timestamp" in result


def test_read_vibration_values_within_spec():
    gw = MockGateway(seed=123)
    for _ in range(100):
        result = gw.read_vibration()
        assert 0 <= result["accel_rms_mg"] <= 500
        assert 0 <= result["velocity_rms_mms"] <= 50
        assert 0 <= result["peak_accel_mg"] <= 800
        assert -10 <= result["temperature_c"] <= 100


def test_read_temp_humidity_returns_valid_dict():
    gw = MockGateway(seed=42)
    result = gw.read_temp_humidity()
    assert result["sensor_id"] == "ES35-SW"
    assert "temperature_c" in result
    assert "humidity_pct" in result
    assert "timestamp" in result


def test_read_temp_humidity_values_within_spec():
    gw = MockGateway(seed=456)
    for _ in range(100):
        result = gw.read_temp_humidity()
        assert -10 <= result["temperature_c"] <= 100
        assert 0 <= result["humidity_pct"] <= 100


def test_read_load_returns_valid_dict():
    gw = MockGateway(seed=42)
    result = gw.read_load()
    assert result["sensor_id"] == "RW-ST01D"
    assert "load_kg" in result
    assert "timestamp" in result


def test_read_load_values_within_spec():
    gw = MockGateway(seed=789)
    for _ in range(100):
        result = gw.read_load()
        assert 0 <= result["load_kg"] <= 2000


def test_fixed_seed_reproducible():
    gw1 = MockGateway(seed=42)
    gw2 = MockGateway(seed=42)
    results1 = [gw1.read_vibration() for _ in range(10)]
    results2 = [gw2.read_vibration() for _ in range(10)]
    for r1, r2 in zip(results1, results2):
        assert r1["accel_rms_mg"] == pytest.approx(r2["accel_rms_mg"])
        assert r1["peak_accel_mg"] == pytest.approx(r2["peak_accel_mg"])
