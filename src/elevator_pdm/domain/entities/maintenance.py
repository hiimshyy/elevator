"""Maintenance schedule domain entity."""
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class MaintenanceSchedule:
    """AI-generated or manual maintenance recommendation."""

    elevator_id: str
    recommended_date: str  # ISO date
    urgency: str  # routine | soon | urgent | immediate
    reason: str  # e.g. 'Vibration anomaly sustained 48h'
    estimated_rul_hours: float | None = None
    status: str = "pending"  # pending | scheduled | completed | cancelled
    completed_at: str | None = None
    technician: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    id: int | None = None
