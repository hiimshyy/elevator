"""Feature engineer service — computes rolling features from sensor readings."""
from collections import deque
from typing import Optional, Dict
import statistics


class FeatureEngineer:
    """Compute all 11 rolling features from sensor readings.

    Maintains internal ring buffers for rolling window calculations.
    """

    def __init__(self, max_capacity_kg: float = 1000) -> None:
        self._max_capacity_kg = max_capacity_kg

        # 10-minute windows (assuming 5s poll interval = 120 readings)
        self._accel_window = deque(maxlen=120)
        # 1-hour window (3600s / 5s = 720 readings)
        self._velocity_window = deque(maxlen=720)
        # 30-minute window (1800s / 5s = 360 readings)
        self._humidity_window = deque(maxlen=360)
        # 5-minute window (300s / 5s = 60 readings)
        self._load_window = deque(maxlen=60)

        # For accel_roc (rate of change)
        self._prev_accel_rms: Optional[float] = None

        # For multivariate score (last computed features)
        self._last_features: Optional[Dict[str, float]] = None

    def compute(self, reading: Dict[str, Optional[float]]) -> Dict[str, float]:
        """Compute all features from a single sensor reading.

        Args:
            reading: Dict with sensor reading values

        Returns:
            Dict with all 11 computed features (no NaN values)
        """
        features = {}

        # Extract values
        accel_rms = reading.get("accel_rms_mg")
        velocity_rms = reading.get("velocity_rms_mms")
        peak_accel = reading.get("peak_accel_mg")
        vib_temp = reading.get("vib_temperature_c")
        env_temp = reading.get("env_temperature_c")
        humidity = reading.get("env_humidity_pct")
        load_kg = reading.get("load_kg")

        # 1. accel_rms_mean — mean of accel_rms over 10min window
        if accel_rms is not None:
            self._accel_window.append(accel_rms)
        if len(self._accel_window) > 0:
            features["accel_rms_mean"] = statistics.mean(self._accel_window)
        else:
            features["accel_rms_mean"] = 0.0

        # 2. accel_rms_std — std of accel_rms over 10min window
        if len(self._accel_window) >= 2:
            features["accel_rms_std"] = statistics.stdev(self._accel_window)
        else:
            features["accel_rms_std"] = 0.0

        # 3. accel_delta — current − rolling_mean
        if accel_rms is not None:
            features["accel_delta"] = accel_rms - features["accel_rms_mean"]
        else:
            features["accel_delta"] = 0.0

        # 4. accel_roc — rate of change (current - previous) / interval
        if accel_rms is not None and self._prev_accel_rms is not None:
            features["accel_roc"] = (accel_rms - self._prev_accel_rms) / 5.0
        else:
            features["accel_roc"] = 0.0
        if accel_rms is not None:
            self._prev_accel_rms = accel_rms

        # 5. velocity_rms_z — Z-score: (x − mean) / std over 1 hour
        if velocity_rms is not None:
            self._velocity_window.append(velocity_rms)
        if len(self._velocity_window) >= 2 and velocity_rms is not None:
            v_mean = statistics.mean(self._velocity_window)
            v_std = statistics.stdev(self._velocity_window)
            features["velocity_rms_z"] = (velocity_rms - v_mean) / v_std if v_std > 0 else 0.0
        else:
            features["velocity_rms_z"] = 0.0

        # 6. peak_to_rms_ratio — peak_accel / accel_rms
        if peak_accel is not None and accel_rms is not None and accel_rms > 0:
            features["peak_to_rms_ratio"] = peak_accel / accel_rms
        else:
            features["peak_to_rms_ratio"] = 0.0

        # 7. motor_temp_delta — vib_temp - env_temp
        if vib_temp is not None and env_temp is not None:
            features["motor_temp_delta"] = vib_temp - env_temp
        else:
            features["motor_temp_delta"] = 0.0

        # 8. humidity_trend — slope of humidity over 30min window
        if humidity is not None:
            self._humidity_window.append(humidity)
        if len(self._humidity_window) >= 2:
            # Simple linear regression slope
            n = len(self._humidity_window)
            x_mean = (n - 1) / 2.0
            y_mean = statistics.mean(self._humidity_window)
            numerator = sum(
                (i - x_mean) * (y - y_mean)
                for i, y in enumerate(self._humidity_window)
            )
            denominator = sum((i - x_mean) ** 2 for i in range(n))
            features["humidity_trend"] = numerator / denominator if denominator > 0 else 0.0
        else:
            features["humidity_trend"] = 0.0

        # 9. load_pct — load_kg / max_capacity
        if load_kg is not None and self._max_capacity_kg > 0:
            features["load_pct"] = load_kg / self._max_capacity_kg
        else:
            features["load_pct"] = 0.0

        # 10. load_variance — std of load_kg over 5min window
        if load_kg is not None:
            self._load_window.append(load_kg)
        if len(self._load_window) >= 2:
            features["load_variance"] = statistics.stdev(self._load_window)
        else:
            features["load_variance"] = 0.0

        # 11. multivariate_score — composite of all features
        features["multivariate_score"] = self._compute_multivariate_score(features)

        # Store for potential future use
        self._last_features = features.copy()

        return features

    def _compute_multivariate_score(self, features: Dict[str, float]) -> float:
        """Compute multivariate score from all features.

        Returns a normalized score between 0 and 1.
        """
        # Simple weighted combination (can be replaced with ML model)
        score = 0.0

        # Accel components (weight: 0.3)
        if "accel_rms_mean" in features:
            score += 0.1 * min(features["accel_rms_mean"] / 500.0, 1.0)
        if "accel_rms_std" in features:
            score += 0.1 * min(features["accel_rms_std"] / 100.0, 1.0)
        if "accel_delta" in features:
            score += 0.05 * min(abs(features["accel_delta"]) / 100.0, 1.0)
        if "accel_roc" in features:
            score += 0.05 * min(abs(features["accel_roc"]) / 50.0, 1.0)

        # Velocity Z-score (weight: 0.2)
        if "velocity_rms_z" in features:
            score += 0.2 * min(abs(features["velocity_rms_z"]) / 3.0, 1.0)

        # Peak to RMS (weight: 0.1)
        if "peak_to_rms_ratio" in features:
            score += 0.1 * min(features["peak_to_rms_ratio"] / 5.0, 1.0)

        # Temperature delta (weight: 0.1)
        if "motor_temp_delta" in features:
            score += 0.1 * min(abs(features["motor_temp_delta"]) / 30.0, 1.0)

        # Humidity trend (weight: 0.05)
        if "humidity_trend" in features:
            score += 0.05 * min(abs(features["humidity_trend"]) / 10.0, 1.0)

        # Load components (weight: 0.2)
        if "load_pct" in features:
            score += 0.1 * min(features["load_pct"], 1.0)
        if "load_variance" in features:
            score += 0.1 * min(features["load_variance"] / 500.0, 1.0)

        return min(max(score, 0.0), 1.0)

    def get_last_features(self) -> Optional[Dict[str, float]]:
        """Get the last computed feature vector."""
        return self._last_features.copy() if self._last_features else None

    def reset(self) -> None:
        """Reset all internal buffers."""
        self._accel_window.clear()
        self._velocity_window.clear()
        self._humidity_window.clear()
        self._load_window.clear()
        self._prev_accel_rms = None
        self._last_features = None
