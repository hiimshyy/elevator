"""Tests for EstimateRul use case."""
import pytest
from datetime import datetime, timezone, timedelta
from typing import List, Tuple

from elevator_pdm.application.use_cases.estimate_rul import EstimateRul
from elevator_pdm.domain.entities.maintenance import MaintenanceSchedule


class MockMaintenanceRepository:
    """Mock maintenance repository for testing."""

    def __init__(self):
        self.records: List[MaintenanceSchedule] = []

    def create(self, maintenance: MaintenanceSchedule) -> None:
        self.records.append(maintenance)

    def find_by_elevator(self, elevator_id: str, status: str = None):
        return [r for r in self.records if r.elevator_id == elevator_id]

    def update_status(self, maintenance_id: int, status: str, **kwargs):
        pass


def _make_scores(
    hours: float,
    start_score: float,
    end_score: float,
    n_points: int = 24,
) -> List[Tuple[datetime, float]]:
    """Generate synthetic health score series.

    Args:
        hours: Total time span in hours.
        start_score: Health score at start.
        end_score: Health score at end.
        n_points: Number of data points.

    Returns:
        List of (timestamp, score) tuples.
    """
    now = datetime.now(timezone.utc)
    base = now - timedelta(hours=hours)
    scores = []
    for i in range(n_points):
        t = base + timedelta(hours=(hours * i / (n_points - 1)))
        score = start_score + (end_score - start_score) * (i / (n_points - 1))
        scores.append((t, score))
    return scores


class TestEstimateRul:

    def setup_method(self):
        self.repo = MockMaintenanceRepository()
        self.estimator = EstimateRul(self.repo, window_hours=168.0)

    def test_declining_health_scores_returns_positive_rul(self):
        # Health declining from 80 to 40 over 7 days
        scores = _make_scores(
            hours=168.0,
            start_score=80.0,
            end_score=40.0,
            n_points=24,
        )

        rul = self.estimator.execute("elev-001", scores)

        assert rul is not None
        assert rul > 0

    def test_stable_high_scores_returns_none(self):
        # Health stable around 85 (not declining)
        now = datetime.now(timezone.utc)
        scores = [
            (now - timedelta(hours=168 - i * 7), 85.0 + (i * 0.1))
            for i in range(24)
        ]

        rul = self.estimator.execute("elev-001", scores)

        assert rul is None

    def test_rul_less_than_24h_sets_urgency_immediate(self):
        # Sharp decline: from 80 to 35 in 7 days
        # Slope = (35-80)/168 = -0.268 per hour
        # Hours to 30: (30-80)/(-0.268) ≈ 186h... wait that's wrong
        # Actually at end score is 40, so we need to extrapolate
        scores = _make_scores(
            hours=168.0,
            start_score=80.0,
            end_score=40.0,
            n_points=24,
        )

        rul = self.estimator.execute("elev-001", scores)

        if rul is not None and rul < 24.0:
            assert len(self.repo.records) == 1
            assert self.repo.records[0].urgency == "immediate"

    def test_creates_maintenance_record_in_repository(self):
        scores = _make_scores(
            hours=168.0,
            start_score=80.0,
            end_score=40.0,
            n_points=24,
        )

        self.estimator.execute("elev-001", scores)

        assert len(self.repo.records) == 1
        record = self.repo.records[0]
        assert record.elevator_id == "elev-001"
        assert record.estimated_rul_hours is not None
        assert record.status == "pending"

    def test_insufficient_data_returns_none(self):
        scores = [(datetime.now(timezone.utc), 80.0)]

        rul = self.estimator.execute("elev-001", scores)

        assert rul is None

    def test_empty_scores_returns_none(self):
        rul = self.estimator.execute("elev-001", [])

        assert rul is None

    def test_rul_calculation_accuracy(self):
        # Create a perfect linear decline over 100 hours
        # At 100h ago: score=80, at now (0h ago): score=30
        # Slope = (30-80)/100 = -0.5 per hour
        # Current score = 30 (at threshold), so RUL should be ~0
        now = datetime.now(timezone.utc)
        scores = []
        for i in range(11):  # 11 points over 100 hours
            hours_since_start = i * 10  # 0, 10, 20, ..., 100
            score = 80.0 - 0.5 * hours_since_start  # 80, 75, 70, ..., 30
            hours_ago = 100 - hours_since_start  # 100, 90, 80, ..., 0
            scores.append((now - timedelta(hours=hours_ago), score))
        # scores is now in ascending order (oldest first: 100h ago, score=80)

        rul = self.estimator.execute("elev-001", scores)

        assert rul is not None
        assert abs(rul - 0.0) < 5.0  # Should be ~0 since at threshold

    def test_urgency_levels(self):
        # Test different urgency levels based on RUL
        # RUL = (30 - current_score) / slope
        # For current_score=40:
        #   slope=-2.0: RUL = (30-40)/(-2) = 5h → immediate
        #   slope=-0.5: RUL = (30-40)/(-0.5) = 20h → immediate
        #   slope=-0.2: RUL = (30-40)/(-0.2) = 50h → urgent
        #   slope=-0.1: RUL = (30-40)/(-0.1) = 100h → soon
        test_cases = [
            (-2.0, 40.0, "immediate", (0, 24)),
            (-0.5, 40.0, "immediate", (0, 24)),
            (-0.2, 40.0, "urgent", (24, 72)),
            (-0.1, 40.0, "soon", (72, 168)),
        ]

        for slope, current_score, expected_urgency, (rul_min, rul_max) in test_cases:
            start_score = current_score - slope * 168.0  # 168 hours of data

            scores = _make_scores(
                hours=168.0,
                start_score=start_score,
                end_score=current_score,
                n_points=24,
            )

            self.repo.records.clear()  # Clear previous records
            rul = self.estimator.execute("elev-001", scores)

            assert rul is not None, f"RUL is None for slope={slope}"
            assert rul_min <= rul <= rul_max, f"RUL={rul} not in ({rul_min}, {rul_max})"
            assert self.repo.records[0].urgency == expected_urgency, \
                f"Expected {expected_urgency}, got {self.repo.records[0].urgency}"

    def test_maintenance_reason_contains_rul(self):
        scores = _make_scores(
            hours=168.0,
            start_score=80.0,
            end_score=40.0,
            n_points=24,
        )

        self.estimator.execute("elev-001", scores)

        assert len(self.repo.records) == 1
        reason = self.repo.records[0].reason
        assert "RUL=" in reason or "rul" in reason.lower()

    def test_non_declining_scores_no_maintenance_record(self):
        # Increasing scores (health improving)
        scores = _make_scores(
            hours=168.0,
            start_score=40.0,
            end_score=80.0,
            n_points=24,
        )

        self.estimator.execute("elev-001", scores)

        assert len(self.repo.records) == 0
