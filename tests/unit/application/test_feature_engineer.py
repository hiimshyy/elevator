"""Tests for FeatureEngineer service."""
import pytest

from elevator_pdm.application.services.feature_engineer import FeatureEngineer


def test_computes_all_11_features():
    fe = FeatureEngineer(max_capacity_kg=1000)

    reading = {
        "accel_rms_mg": 42.5,
        "velocity_rms_mms": 12.3,
        "peak_accel_mg": 98.0,
        "vib_temperature_c": 25.0,
        "env_temperature_c": 23.0,
        "env_humidity_pct": 60.0,
        "load_kg": 450.0,
    }

    features = fe.compute(reading)

    # Check all 11 features are present
    expected_features = [
        "accel_rms_mean", "accel_rms_std", "accel_delta", "accel_roc",
        "velocity_rms_z", "peak_to_rms_ratio", "motor_temp_delta",
        "humidity_trend", "load_pct", "load_variance", "multivariate_score"
    ]
    for feat in expected_features:
        assert feat in features, f"Missing feature: {feat}"

    # No NaN values
    for feat, value in features.items():
        assert value is not None, f"Feature {feat} is None"
        assert not (isinstance(value, float) and __import__('math').isnan(value)), f"Feature {feat} is NaN"


def test_accel_rms_mean_correct_with_120_readings():
    fe = FeatureEngineer(max_capacity_kg=1000)

    # Feed 120 readings
    for i in range(120):
        reading = {"accel_rms_mg": 50.0 + i * 0.1}
        features = fe.compute(reading)

    # Mean should be close to the average of all 120 values
    assert features["accel_rms_mean"] == pytest.approx(55.95, rel=0.01)


def test_accel_rms_std_correct():
    fe = FeatureEngineer(max_capacity_kg=1000)

    # Feed the same value 10 times
    features = None
    for _ in range(10):
        reading = {"accel_rms_mg": 50.0}
        features = fe.compute(reading)

    # Std of constant values is 0
    assert features["accel_rms_std"] == 0.0

    # Now feed varying values
    fe.reset()
    for i in range(10):
        reading = {"accel_rms_mg": float(i * 10)}
        features = fe.compute(reading)

    # Std of [0, 10, 20, ..., 90] using sample std (statistics.stdev)
    # Mean=45, sum of squared deviations=8200, sample variance=911.11, std≈30.185
    assert features["accel_rms_std"] == pytest.approx(30.28, rel=0.01)


def test_accel_delta_with_known_values():
    fe = FeatureEngineer(max_capacity_kg=1000)

    # First reading: delta should be 0 (mean = current)
    reading1 = {"accel_rms_mg": 50.0}
    features1 = fe.compute(reading1)
    assert features1["accel_delta"] == pytest.approx(0.0, abs=0.01)

    # Second reading: mean = (50 + 60) / 2 = 55, delta = 60 - 55 = 5
    reading2 = {"accel_rms_mg": 60.0}
    features2 = fe.compute(reading2)
    assert features2["accel_delta"] == pytest.approx(5.0, abs=0.01)


def test_accel_roc_computes_rate_of_change():
    fe = FeatureEngineer(max_capacity_kg=1000)

    # First reading: no previous, roc should be 0
    reading1 = {"accel_rms_mg": 50.0}
    features1 = fe.compute(reading1)
    assert features1["accel_roc"] == 0.0

    # Second reading: (60 - 50) / 5 = 2.0
    reading2 = {"accel_rms_mg": 60.0}
    features2 = fe.compute(reading2)
    assert features2["accel_roc"] == pytest.approx(2.0, abs=0.01)


def test_z_score_returns_zero_for_mean_valued_input():
    fe = FeatureEngineer(max_capacity_kg=1000)

    # Feed many readings with same value
    for _ in range(100):
        reading = {"velocity_rms_mms": 12.3}
        features = fe.compute(reading)

    # Z-score of mean-valued input should be 0
    assert features["velocity_rms_z"] == pytest.approx(0.0, abs=0.01)


def test_peak_to_rms_ratio():
    fe = FeatureEngineer(max_capacity_kg=1000)

    reading = {
        "accel_rms_mg": 50.0,
        "peak_accel_mg": 150.0,
    }
    features = fe.compute(reading)

    # ratio = 150 / 50 = 3.0
    assert features["peak_to_rms_ratio"] == pytest.approx(3.0, abs=0.01)


def test_motor_temp_delta():
    fe = FeatureEngineer(max_capacity_kg=1000)

    reading = {
        "vib_temperature_c": 25.0,
        "env_temperature_c": 22.0,
    }
    features = fe.compute(reading)

    # delta = 25 - 22 = 3
    assert features["motor_temp_delta"] == 3.0


def test_humidity_trend():
    fe = FeatureEngineer(max_capacity_kg=1000)

    # Feed increasing humidity values
    for i in range(10):
        reading = {"env_humidity_pct": 50.0 + i}
        features = fe.compute(reading)

    # Trend should be positive
    assert features["humidity_trend"] > 0


def test_load_pct_exact():
    fe = FeatureEngineer(max_capacity_kg=1000)

    reading = {"load_kg": 450.0}
    features = fe.compute(reading)

    # load_pct = 450 / 1000 = 0.45
    assert features["load_pct"] == pytest.approx(0.45, abs=0.01)


def test_load_variance():
    fe = FeatureEngineer(max_capacity_kg=1000)

    # Feed varying load values
    for i in range(10):
        reading = {"load_kg": float(i * 50)}
        features = fe.compute(reading)

    # Variance should be > 0
    assert features["load_variance"] > 0


def test_returns_complete_feature_dict_no_nan():
    fe = FeatureEngineer(max_capacity_kg=1000)

    reading = {
        "accel_rms_mg": 42.5,
        "velocity_rms_mms": 12.3,
        "peak_accel_mg": 98.0,
        "vib_temperature_c": 25.0,
        "env_temperature_c": 23.0,
        "env_humidity_pct": 60.0,
        "load_kg": 450.0,
    }

    features = fe.compute(reading)

    # All features present and no NaN
    assert len(features) == 11

    import math
    for key, value in features.items():
        assert not math.isnan(value), f"{key} is NaN"
        assert not math.isinf(value), f"{key} is Infinity"


def test_get_last_features():
    fe = FeatureEngineer(max_capacity_kg=1000)

    reading = {"accel_rms_mg": 42.5, "load_kg": 450.0}
    features = fe.compute(reading)

    last = fe.get_last_features()
    assert last is not None
    assert last["accel_rms_mg" if "accel_rms_mg" in last else "accel_rms_mean"] == features.get("accel_rms_mean") or features.get("accel_rms_mg")


def test_reset_clears_buffers():
    fe = FeatureEngineer(max_capacity_kg=1000)

    # Feed some data
    for i in range(10):
        reading = {"accel_rms_mg": float(i * 10), "load_kg": float(i * 50)}
        fe.compute(reading)

    # Reset
    fe.reset()

    # Buffers should be empty
    assert len(fe._accel_window) == 0
    assert len(fe._load_window) == 0
    assert fe._prev_accel_rms is None
    assert fe._last_features is None


def test_handles_missing_fields_gracefully():
    fe = FeatureEngineer(max_capacity_kg=1000)

    # Reading with only some fields
    reading = {"accel_rms_mg": 42.5}
    features = fe.compute(reading)

    # Should still return all features with defaults for missing
    assert len(features) == 11
    assert features["load_pct"] == 0.0  # Missing load_kg
    assert features["motor_temp_delta"] == 0.0  # Missing temp fields
