"""Elevator domain entity."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Elevator:
    """Core elevator entity representing a physical elevator unit."""

    id: str  # UUID v4
    name: str  # e.g. 'Tower A - Lift 3'
    location: str  # Building / floor / shaft
    max_capacity_kg: float
    install_date: str  # ISO date
    status: str = "active"  # active | decommissioned | maintenance
    last_maintenance: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
