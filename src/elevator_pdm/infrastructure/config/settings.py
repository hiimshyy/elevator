import os
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic_settings.sources import YamlConfigSettingsSource

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
CONFIG_YAML_PATH = os.path.join(BASE_DIR, "config", "config.yaml")


class SerialConfig(BaseModel):
    port: str = "/dev/ttyUSB0"
    baudrate: int = 9600
    timeout_s: float = 1.0


class SensorConfig(BaseModel):
    slave_id: int = 1
    poll_interval_s: int = 5
    model: str = ""


class SensorsConfig(BaseModel):
    vibration: SensorConfig = SensorConfig(slave_id=1, poll_interval_s=5, model="ES-VS-01")
    temp_humid: SensorConfig = SensorConfig(slave_id=2, poll_interval_s=30, model="ES35-SW")
    load: SensorConfig = SensorConfig(slave_id=3, poll_interval_s=1, model="RW-ST01D")


class ElevatorConfig(BaseModel):
    id: str = "elev-001"
    max_capacity_kg: int = 1000


class ThresholdsConfig(BaseModel):
    accel_rms_warning_mg: int = 80
    accel_rms_critical_mg: int = 150
    load_overload_pct: float = 0.95
    motor_temp_warning_c: int = 65
    motor_temp_critical_c: int = 80


class ModelsConfig(BaseModel):
    vibration_anomaly: str = "models/vibration_anomaly_v1.onnx"
    health_score: str = "models/health_score_v1.onnx"


class AlertsConfig(BaseModel):
    rate_limit_minutes: int = 15
    slack_webhook: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_from: str = ""
    smtp_to: list[str] = []


class Settings(BaseSettings):
    serial: SerialConfig = SerialConfig()
    sensors: SensorsConfig = SensorsConfig()
    elevator: ElevatorConfig = ElevatorConfig()
    thresholds: ThresholdsConfig = ThresholdsConfig()
    models: ModelsConfig = ModelsConfig()
    alerts: AlertsConfig = AlertsConfig()

    model_config = SettingsConfigDict(env_prefix="ELEVATOR_", env_nested_delimiter="__")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        return (
            init_settings,
            env_settings,
            YamlConfigSettingsSource(settings_cls, CONFIG_YAML_PATH),
            dotenv_settings,
            file_secret_settings,
        )
