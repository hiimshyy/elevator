"""Maintenance schedule domain entity."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class MaintenanceSchedule:
    """AI-generated or manual maintenance recommendation."""

    elevator_id: str
    recommended_date: str  # ISO date
    urgency: str  # routine | soon | urgent | immediate
    reason: str  # e.g. 'Vibration anomaly sustained 48h'
    estimated_rul_hours: Optional[float] = None
    status: str = "pending"  # pending | scheduled | completed | cancelled
    completed_at: Optional[str] = None
    technician: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
