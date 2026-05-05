"""Tests for EvaluateRulesUseCase."""
import pytest

from elevator_pdm.application.use_cases.evaluate_rules import EvaluateRulesUseCase
from elevator_pdm.infrastructure.config.settings import Settings


def test_returns_normal_when_all_values_within_range():
    rules = EvaluateRulesUseCase()

    # All values within normal range
    result = rules.execute(
        accel_rms_mg=42.5,  # < 80mg WARNING threshold
        load_pct=0.50,     # < 0.95 OVERLOAD threshold
        motor_temp_c=25.0,  # < 65°C WARNING threshold
    )

    assert result == "NORMAL"


def test_returns_warning_for_accel_rms():
    rules = EvaluateRulesUseCase()

    # accel_rms > 80mg → WARNING
    result = rules.execute(accel_rms_mg=100.0)

    assert result == "WARNING"


def test_returns_critical_for_accel_rms():
    rules = EvaluateRulesUseCase()

    # accel_rms > 150mg → CRITICAL
    result = rules.execute(accel_rms_mg=200.0)

    assert result == "CRITICAL"


def test_returns_overload_for_load_pct():
    rules = EvaluateRulesUseCase()

    # load > 95% capacity → OVERLOAD
    result = rules.execute(load_pct=0.96)

    assert result == "OVERLOAD"


def test_returns_warning_for_motor_temp():
    rules = EvaluateRulesUseCase()

    # motor_temp > 65°C → WARNING
    result = rules.execute(motor_temp_c=70.0)

    assert result == "WARNING"


def test_returns_critical_for_motor_temp():
    rules = EvaluateRulesUseCase()

    # motor_temp > 80°C → CRITICAL
    result = rules.execute(motor_temp_c=85.0)

    assert result == "CRITICAL"


def test_multiple_breaches_return_highest_severity():
    rules = EvaluateRulesUseCase()

    # Multiple breaches: accel WARNING + temp CRITICAL → CRITICAL
    result = rules.execute(
        accel_rms_mg=100.0,  # WARNING
        motor_temp_c=85.0,   # CRITICAL
    )

    assert result == "CRITICAL"


def test_overload_higher_than_critical():
    rules = EvaluateRulesUseCase()

    # OVERLOAD should be higher than CRITICAL
    result = rules.execute(
        accel_rms_mg=200.0,  # CRITICAL
        load_pct=0.96,        # OVERLOAD
    )

    assert result == "OVERLOAD"


def test_partial_data_evaluation():
    rules = EvaluateRulesUseCase()

    # Only check what's provided
    result = rules.execute(accel_rms_mg=42.5)  # Normal
    assert result == "NORMAL"

    result = rules.execute(accel_rms_mg=100.0)  # Warning
    assert result == "WARNING"


def test_thresholds_from_settings():
    """Test that thresholds are configurable via Settings."""
    settings = Settings()
    # Override thresholds
    settings.thresholds.accel_rms_warning_mg = 50
    settings.thresholds.accel_rms_critical_mg = 100

    rules = EvaluateRulesUseCase(settings)

    # Now 60mg should trigger WARNING
    result = rules.execute(accel_rms_mg=60.0)
    assert result == "WARNING"

    # 110mg should trigger CRITICAL
    result = rules.execute(accel_rms_mg=110.0)
    assert result == "CRITICAL"


def test_all_normal_with_none_values():
    rules = EvaluateRulesUseCase()

    # Passing None should return NORMAL
    result = rules.execute(
        accel_rms_mg=None,
        load_pct=None,
        motor_temp_c=None,
    )

    assert result == "NORMAL"


def test_critical_accel_with_normal_temp():
    rules = EvaluateRulesUseCase()

    result = rules.execute(
        accel_rms_mg=200.0,  # CRITICAL
        motor_temp_c=25.0,   # Normal
    )

    assert result == "CRITICAL"


def test_normal_accel_with_critical_temp():
    rules = EvaluateRulesUseCase()

    result = rules.execute(
        accel_rms_mg=42.5,   # Normal
        motor_temp_c=85.0,  # CRITICAL
    )

    assert result == "CRITICAL"
