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

    regCurrentFloor: int = 0x2111
    regInsideCall: int = 0x2013
    regUpCall: int = 0x2017
    regDownCall: int = 0x2021
    regRunNumberLow: int = 0x2100
    regRunNumberBitHigh: int = 0x2101
    regCurrentHeight: int = 0x2110
    regCurrentFloor: int = 0x2111
    regFloorReached: int = 0x2113
    regSourceVoltage: int = 0x2114
    regCTBInput: int = 0x2117
    regOutputStatus: int = 0x2118
    regRunningSpeed: int = 0x2119
    regOperatingStatus: int = 0x2120
    regCurrent: int = 0x2121
    regVoltage: int = 0x2122
    regTotalErrorCount: int = 0x3000
    regCurrentErrorCount: int = 0x3001

    # Error Code 1
    regErrorCode1: int = 0x3002
    regError1Year: int = 0x3003
    regError1MonthDay: int = 0x3004
    regError1HourMin: int = 0x3005
    regError1MinSec: int = 0x3006
    regError1Floor: int = 0x3007
    regInputState1: int = 0x3008
    regInputState2: int = 0x3009
    regOutputState: int = 0x3010
    regError1Speed: int = 0x3011
    regError1Position: int = 0x3012
    regError1Voltage: int = 0x3013
    regError1Current: int = 0x3014
    regError1Frequency: int = 0x3015

    # Error Code 2
    regErrorCode2: int = 0x3022
    regError2Year: int = 0x3023
    regError2MonthDay: int = 0x3024
    regError2HourMin: int = 0x3025
    regError2MinSec: int = 0x3026
    regError2Floor: int = 0x3027
    regInputState3: int = 0x3028
    regInputState4: int = 0x3029
    regOutputState2: int = 0x3030
    regError2Speed: int = 0x3031
    regError2Position: int = 0x3032
    regError2Voltage: int = 0x3033
    regError2Current: int = 0x3034
    regError2Frequency: int = 0x3035

    # Error Code 3
    regErrorCode3: int = 0x3042
    regError3Year: int = 0x3043
    regError3MonthDay: int = 0x3044
    regError3HourMin: int = 0x3045
    regError3MinSec: int = 0x3046
    regError3Floor: int = 0x3047
    regInputState5: int = 0x3048
    regInputState6: int = 0x3049
    regOutputState3: int = 0x3050
    regError3Speed: int = 0x3051
    regError3Position: int = 0x3052
    regError3Voltage: int = 0x3053
    regError3Current: int = 0x3054
    regError3Frequency: int = 0x3055

    # Error Code 4
    regErrorCode4: int = 0x3062
    regError4Year: int = 0x3063
    regError4MonthDay: int = 0x3064
    regError4HourMin: int = 0x3065
    regError4MinSec: int = 0x3066
    regError4Floor: int = 0x3067
    regInputState7: int = 0x3068
    regInputState8: int = 0x3069
    regOutputState4: int = 0x3070
    regError4Speed: int = 0x3071
    regError4Position: int = 0x3072
    regError4Voltage: int = 0x3073
    regError4Current: int = 0x3074
    regError4Frequency: int = 0x3075

    # Error Code 5
    regErrorCode5: int = 0x3082
    regError5Year: int = 0x3083
    regError5MonthDay: int = 0x3084
    regError5HourMin: int = 0x3085
    regError5MinSec: int = 0x3086
    regError5Floor: int = 0x3087
    regInputState9: int = 0x3088
    regInputState10: int = 0x3089
    regOutputState5: int = 0x3090
    regError5Speed: int = 0x3091
    regError5Position: int = 0x3092
    regError5Voltage: int = 0x3093
    regError5Current: int = 0x3094
    regError5Frequency: int = 0x3095

    # Error Code 6
    regErrorCode6: int = 0x3102
    regError6Year: int = 0x3103
    regError6MonthDay: int = 0x3104
    regError6HourMin: int = 0x3105
    regError6MinSec: int = 0x3106
    regError6Floor: int = 0x3107
    regInputState11: int = 0x3108
    regInputState12: int = 0x3109
    regOutputState6: int = 0x3110
    regError6Speed: int = 0x3111
    regError6Position: int = 0x3112
    regError6Voltage: int = 0x3113
    regError6Current: int = 0x3114
    regError6Frequency: int = 0x3115

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
