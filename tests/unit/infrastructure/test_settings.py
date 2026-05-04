import os
import pytest
from src.elevator_pdm.infrastructure.config.settings import Settings, CONFIG_YAML_PATH, SensorConfig


def test_loads_from_config_yaml():
    settings = Settings()
    assert settings.serial.port == "/dev/ttyUSB0"
    assert settings.serial.baudrate == 9600
    assert settings.sensors.vibration.slave_id == 1
    assert settings.sensors.vibration.poll_interval_s == 5
    assert settings.sensors.vibration.model == "ES-VS-01"
    assert settings.sensors.temp_humid.slave_id == 2
    assert settings.sensors.load.slave_id == 3
    assert settings.thresholds.accel_rms_warning_mg == 80
    assert settings.thresholds.accel_rms_critical_mg == 150
    assert settings.elevator.max_capacity_kg == 1000
    assert settings.models.vibration_anomaly == "models/vibration_anomaly_v1.onnx"
    assert settings.alerts.rate_limit_minutes == 15


def test_env_vars_override_yaml(monkeypatch):
    monkeypatch.setenv("ELEVATOR_SERIAL__PORT", "/dev/ttyUSB1")
    settings = Settings()
    assert settings.serial.port == "/dev/ttyUSB1"
    assert settings.sensors.vibration.slave_id == 1  # Unchanged


def test_missing_field_raises_error():
    with pytest.raises(Exception):
        Settings(serial=None)


def test_defaults_when_not_in_yaml(tmp_path):
    temp_yaml = tmp_path / "temp_config.yaml"
    temp_yaml.write_text("serial:\n  port: /dev/ttyUSB5")

    from pydantic_settings import BaseSettings, SettingsConfigDict
    from pydantic_settings.sources import YamlConfigSettingsSource

    class TestSettings(BaseSettings):
        serial: dict = {"port": "/dev/ttyUSB0", "baudrate": 9600}
        model_config = SettingsConfigDict(env_prefix="TEST_")

        @classmethod
        def settings_customise_sources(cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings):
            return (
                init_settings,
                env_settings,
                YamlConfigSettingsSource(settings_cls, str(temp_yaml)),
                dotenv_settings,
                file_secret_settings,
            )

    settings = TestSettings()
    assert settings.serial["port"] == "/dev/ttyUSB5"
