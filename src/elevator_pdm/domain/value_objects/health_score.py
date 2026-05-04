"""Health score value object."""
from dataclasses import dataclass


@dataclass(frozen=True)
class HealthScore:
    """Composite health score (0–100) with semantic thresholds."""

    value: float

    def __post_init__(self):
        if not 0.0 <= self.value <= 100.0:
            raise ValueError(f"HealthScore must be 0–100, got {self.value}")

    @property
    def level(self) -> str:
        """Return semantic level: GOOD | FAIR | POOR."""
        if self.value >= 70:
            return "GOOD"
        elif self.value >= 40:
            return "FAIR"
        return "POOR"

    @property
    def color(self) -> str:
        """Return display color for dashboards."""
        if self.value >= 70:
            return "green"
        elif self.value >= 40:
            return "yellow"
        return "red"
