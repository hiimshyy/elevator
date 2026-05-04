"""Status and severity enums."""
from enum import Enum


class ElevatorStatus(str, Enum):
    ACTIVE = "active"
    DECOMMISSIONED = "decommissioned"
    MAINTENANCE = "maintenance"


class InferenceStatus(str, Enum):
    NORMAL = "NORMAL"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    OVERLOAD = "OVERLOAD"


class AlertSeverity(str, Enum):
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    EMERGENCY = "EMERGENCY"


class AlertType(str, Enum):
    VIBRATION_HIGH = "VIBRATION_HIGH"
    TEMP_HIGH = "TEMP_HIGH"
    OVERLOAD = "OVERLOAD"
    HEALTH_LOW = "HEALTH_LOW"


class MaintenanceUrgency(str, Enum):
    ROUTINE = "routine"
    SOON = "soon"          # 7 days
    URGENT = "urgent"      # 24 hours
    IMMEDIATE = "immediate"
