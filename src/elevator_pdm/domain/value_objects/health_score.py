"""Health score value object."""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class HealthScore:
    """Composite health score (0–100) with semantic thresholds."""

    value: float

    def __post_init__(self):
        clamped = max(0.0, min(100.0, round(self.value, 2)))
        object.__setattr__(self, 'value', clamped)

    def __eq__(self, other):
        if not isinstance(other, HealthScore):
            return NotImplemented
        return math.isclose(self.value, other.value, abs_tol=0.1)

    def __hash__(self):
        return hash(round(self.value, 1))

    @property
    def color(self) -> str:
        """Return display color for dashboards."""
        if self.value >= 85:
            return "green"
        elif self.value >= 40:
            return "yellow"
        return "red"

    @property
    def status_label(self) -> str:
        """Return human-readable status label."""
        if self.value >= 90:
            return "Healthy"
        elif self.value >= 80:
            return "Good"
        elif self.value >= 60:
            return "Fair"
        elif self.value >= 40:
            return "Poor"
        return "Critical"
