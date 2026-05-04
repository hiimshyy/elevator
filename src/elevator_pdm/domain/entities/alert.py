"""Alert domain entity."""
from dataclasses import dataclass
from typing import Optional


@dataclass
class Alert:
    """Alert raised when inference triggers a threshold breach."""

    elevator_id: str
    inference_id: int
    alert_type: str  # VIBRATION_HIGH | TEMP_HIGH | OVERLOAD | HEALTH_LOW
    severity: str  # WARNING | CRITICAL | EMERGENCY
    message: str  # Human-readable alert message
    sent_at: str  # UTC ISO datetime
    channel: str  # slack | email | sms
    acknowledged: bool = False
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[str] = None
