"""RUL (Remaining Useful Life) estimation use case.

Performs linear regression on health score trend to estimate
hours until maintenance threshold (score=30) is reached.
"""
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from elevator_pdm.domain.entities.maintenance import MaintenanceSchedule
from elevator_pdm.domain.interfaces.maintenance_repository import MaintenanceRepository


# Maintenance threshold - score below this triggers maintenance
MAINTENANCE_THRESHOLD = 30.0

# Urgency thresholds (hours)
IMMEDIATE_THRESHOLD = 24.0
URGENT_THRESHOLD = 72.0
SOON_THRESHOLD = 168.0  # 7 days


class EstimateRul:
    """Estimate Remaining Useful Life from health score trend."""

    def __init__(
        self,
        maintenance_repo: MaintenanceRepository,
        window_hours: float = 168.0,  # 7 days
    ) -> None:
        self._maintenance_repo = maintenance_repo
        self._window_hours = window_hours

    def execute(
        self,
        elevator_id: str,
        health_scores: List[Tuple[datetime, float]],
    ) -> Optional[float]:
        """Estimate RUL from health score trend.

        Args:
            elevator_id: Elevator identifier.
            health_scores: List of (timestamp, score) tuples.
                           Expected to be sorted by timestamp ascending.

        Returns:
            Estimated hours until maintenance threshold (score=30),
            or None if no maintenance needed (stable/high scores).
        """
        if not health_scores or len(health_scores) < 2:
            return None

        # Filter to window and convert to hours-since-first
        now = health_scores[-1][0]
        window_start = now.timestamp() - (self._window_hours * 3600)
        filtered = [
            (ts, score) for ts, score in health_scores
            if ts.timestamp() >= window_start
        ]

        if len(filtered) < 2:
            return None

        # Convert to x=hours_since_first, y=health_score
        first_ts = filtered[0][0]
        x = [(ts - first_ts).total_seconds() / 3600.0 for ts, _ in filtered]
        y = [score for _, score in filtered]

        # Linear regression: y = a + b*x
        n = len(x)
        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(xi * yi for xi, yi in zip(x, y))
        sum_xx = sum(xi * xi for xi in x)

        denominator = n * sum_xx - sum_x * sum_x
        if denominator == 0:
            return None

        b = (n * sum_xy - sum_x * sum_y) / denominator  # slope
        a = (sum_y - b * sum_x) / n  # intercept

        # If slope is non-negative, health is not declining
        if b >= 0:
            return None

        # Calculate hours from NOW to reach maintenance threshold
        # Using slope b (health_score per hour) and current score (y[-1])
        # hours = (threshold - current_score) / b
        if b == 0:
            return None

        hours_to_threshold = (MAINTENANCE_THRESHOLD - y[-1]) / b

        # If already at or below threshold
        if hours_to_threshold <= 0:
            hours_to_threshold = 0.0

        # Create maintenance schedule entry
        self._create_maintenance_entry(
            elevator_id=elevator_id,
            rul_hours=hours_to_threshold,
            current_score=y[-1],
        )

        return hours_to_threshold

    def _create_maintenance_entry(
        self,
        elevator_id: str,
        rul_hours: float,
        current_score: float,
    ) -> None:
        """Create a maintenance schedule entry based on RUL.

        Args:
            elevator_id: Elevator identifier.
            rul_hours: Estimated remaining useful life in hours.
            current_score: Current health score.
        """
        # Determine urgency
        if rul_hours < IMMEDIATE_THRESHOLD:
            urgency = "immediate"
        elif rul_hours < URGENT_THRESHOLD:
            urgency = "urgent"
        elif rul_hours < SOON_THRESHOLD:
            urgency = "soon"
        else:
            urgency = "routine"

        # Calculate recommended date
        now = datetime.now(timezone.utc)
        recommended = now.timestamp() + (rul_hours * 3600)
        recommended_date = datetime.fromtimestamp(recommended, tz=timezone.utc).isoformat()

        # Create reason string
        reason = (
            f"Health score declining: current={current_score:.1f}, "
            f"estimated RUL={rul_hours:.1f}h"
        )

        # Create maintenance schedule
        maintenance = MaintenanceSchedule(
            elevator_id=elevator_id,
            recommended_date=recommended_date,
            urgency=urgency,
            reason=reason,
            estimated_rul_hours=rul_hours,
        )

        self._maintenance_repo.create(maintenance)
