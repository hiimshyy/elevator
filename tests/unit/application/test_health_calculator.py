"""Tests for HealthCalculator service."""
import pytest

from elevator_pdm.application.services.health_calculator import HealthCalculator
from elevator_pdm.domain.value_objects.health_score import HealthScore


def test_all_normal_readings_score_at_least_85():
    calc = HealthCalculator()

    # All-normal: NORMAL status, high confidence
    score = calc.compute_from_status(
        status="NORMAL",
        confidence=0.95,
        trend_direction="stable",
    )

    assert isinstance(score, HealthScore)
    assert score.value >= 85.0
    assert score.value <= 100.0


def test_single_warning_score_40_to_70():
    calc = HealthCalculator()

    # WARNING status
    score = calc.compute_from_status(
        status="WARNING",
        confidence=0.85,
        trend_direction=None,
    )

    assert isinstance(score, HealthScore)
    assert 40.0 <= score.value <= 70.0


def test_critical_score_less_than_40():
    calc = HealthCalculator()

    # CRITICAL status
    score = calc.compute_from_status(
        status="CRITICAL",
        confidence=0.95,
        trend_direction=None,
    )

    assert isinstance(score, HealthScore)
    assert score.value < 40.0


def test_score_never_less_than_0():
    calc = HealthCalculator()

    # Worst case: CRITICAL, low confidence, trend down
    score = calc.compute(
        anomaly_confidence=0.0,  # Model completely unconfident
        rule_severity="OVERLOAD",
        rule_confidence=1.0,
        trend_direction="down",
    )

    assert score.value >= 0.0


def test_score_never_greater_than_100():
    calc = HealthCalculator()

    # Best case: NORMAL, high confidence, trend up
    score = calc.compute(
        anomaly_confidence=1.0,  # Model completely confident
        rule_severity="NORMAL",
        rule_confidence=1.0,
        trend_direction="up",
    )

    assert score.value <= 100.0


def test_returns_valid_health_score_object():
    calc = HealthCalculator()

    score = calc.compute_from_status(
        status="NORMAL",
        confidence=0.90,
    )

    assert isinstance(score, HealthScore)
    assert score.value is not None
    assert score.color in ("green", "yellow", "red")
    assert score.status_label in ("Healthy", "Good", "Fair", "Poor", "Critical")


def test_health_score_color_green_for_high():
    score = HealthScore(value=85.0)
    assert score.color == "green"

    score = HealthScore(value=100.0)
    assert score.color == "green"


def test_health_score_color_yellow_for_medium():
    score = HealthScore(value=70.0)
    assert score.color == "yellow"

    score = HealthScore(value=55.0)
    assert score.color == "yellow"


def test_health_score_color_red_for_low():
    score = HealthScore(value=39.0)
    assert score.color == "red"

    score = HealthScore(value=0.0)
    assert score.color == "red"


def test_health_score_status_labels():
    assert HealthScore(value=90.0).status_label == "Healthy"
    assert HealthScore(value=80.0).status_label == "Good"
    assert HealthScore(value=60.0).status_label == "Fair"
    assert HealthScore(value=45.0).status_label == "Poor"
    assert HealthScore(value=30.0).status_label == "Critical"


def test_compute_with_trend_up():
    calc = HealthCalculator()

    score = calc.compute(
        anomaly_confidence=0.90,
        rule_severity="NORMAL",
        trend_direction="up",
    )

    # Trend up should have slightly higher score
    assert score.value > 90.0


def test_compute_with_trend_down():
    calc = HealthCalculator()

    score = calc.compute(
        anomaly_confidence=0.90,
        rule_severity="NORMAL",
        trend_direction="down",
    )

    # Trend down should penalize
    assert score.value < 95.0


def test_compute_with_overload():
    calc = HealthCalculator()

    score = calc.compute(
        anomaly_confidence=0.80,
        rule_severity="OVERLOAD",
        rule_confidence=1.0,
    )

    # OVERLOAD should give low score
    assert score.value < 50.0


def test_health_score_clamping():
    """Test that scores are clamped to 0-100."""
    # Value > 100 should be clamped
    score = HealthScore(value=150.0)
    assert score.value == 100.0

    # Value < 0 should be clamped
    score = HealthScore(value=-10.0)
    assert score.value == 0.0


def test_health_score_equality():
    score1 = HealthScore(value=85.0)
    score2 = HealthScore(value=85.01)
    assert score1 == score2  # Within tolerance

    score3 = HealthScore(value=90.0)
    assert score1 != score3


def test_different_confidence_levels():
    calc = HealthCalculator()

    # High confidence WARNING
    score_high = calc.compute_from_status(
        status="WARNING",
        confidence=0.95,
    )

    # Low confidence WARNING
    score_low = calc.compute_from_status(
        status="WARNING",
        confidence=0.50,
    )

    # Higher confidence should give lower score (worse health)
    assert score_high.value < score_low.value
