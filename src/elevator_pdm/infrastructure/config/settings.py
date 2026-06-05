import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic_settings.sources import YamlConfigSettingsSource

BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
CONFIG_YAML_PATH = os.path.join(BASE_DIR, "config", "config.yaml")


def _default_database_url() -> str:
    db_path = Path.home() / ".codex" / "memories" / "elevator.db"
    return f"sqlite:///{db_path.as_posix()}"


class SerialConfig(BaseModel):
    port: str = "/dev/ttyUSB0"
    baudrate: int = 19200
    bytesize: int = 8
    parity: str = "E"
    stopbits: int = 1
    timeout_s: float = 1.0


class SensorConfig(BaseModel):
    slave_id: int = 1
    poll_interval_s: int = 5
    model: str = ""


class SensorsConfig(BaseModel):
    source: Literal["mock", "modbus", "hybrid"] = "mock"
    vibration: SensorConfig = SensorConfig(slave_id=1, poll_interval_s=5, model="ES-VS-01")
    temp_humid: SensorConfig = SensorConfig(slave_id=2, poll_interval_s=30, model="ES35-SW")
    load: SensorConfig = SensorConfig(slave_id=3, poll_interval_s=1, model="RW-ST01D")


class ControllerConfig(BaseModel):
    slave_id: int = 1
    register_1047: int = 1047
    register_0x2121: int = 0x2121
    register_0x2122: int = 0x2122
    sensor_id: str = "CTRL-485-01"


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


class MqttConfig(BaseModel):
    broker_url: str = ""
    port: int = 1883
    username: str = ""
    password: str = ""
    topic_r: str = "embody/r"
    topic_w: str = "embody/w"
    client_id: str = "embody002"
    qos: int = 1


class DatabaseConfig(BaseModel):
    url: str = _default_database_url()


class WorkersConfig(BaseModel):
    alert_pipeline_interval_s: int = 30
    alert_pipeline_limit: int = 500


class ApiConfig(BaseModel):
    key: str = "elevator-secret-key-123"


class Settings(BaseSettings):
    serial: SerialConfig = SerialConfig()
    sensors: SensorsConfig = SensorsConfig()
    controller: ControllerConfig = ControllerConfig()
    elevator: ElevatorConfig = ElevatorConfig()
    thresholds: ThresholdsConfig = ThresholdsConfig()
    models: ModelsConfig = ModelsConfig()
    alerts: AlertsConfig = AlertsConfig()
    mqtt: MqttConfig = MqttConfig()
    database: DatabaseConfig = DatabaseConfig()
    workers: WorkersConfig = WorkersConfig()
    api: ApiConfig = ApiConfig()

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
