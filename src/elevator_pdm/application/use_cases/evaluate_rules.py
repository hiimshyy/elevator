"""Rule-Based Overload Detection use case."""
from typing import Optional

from elevator_pdm.infrastructure.config.settings import Settings


class EvaluateRulesUseCase:
    """Apply threshold rules from config.yaml.

    Returns highest severity based on:
    - accel_rms > 80mg → WARNING, > 150mg → CRITICAL
    - load > 95% capacity → OVERLOAD
    - motor_temp > 65°C → WARNING, > 80°C → CRITICAL
    """

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self._settings = settings or Settings()
        self._thresholds = self._settings.thresholds

    def execute(
        self,
        accel_rms_mg: Optional[float] = None,
        load_pct: Optional[float] = None,
        motor_temp_c: Optional[float] = None,
    ) -> str:
        """Evaluate all threshold rules and return highest severity.

        Returns:
            'NORMAL', 'WARNING', 'CRITICAL', or 'OVERLOAD'
        """
        max_severity = "NORMAL"

        # Helper to upgrade severity
        def _upgrade(severity: str) -> None:
            nonlocal max_severity
            severity_order = {"NORMAL": 0, "WARNING": 1, "CRITICAL": 2, "OVERLOAD": 3}
            if severity_order.get(severity, 0) > severity_order.get(max_severity, 0):
                max_severity = severity

        # Check accel_rms thresholds
        if accel_rms_mg is not None:
            if accel_rms_mg > self._thresholds.accel_rms_warning_mg:
                _upgrade("WARNING")
            if accel_rms_mg > self._thresholds.accel_rms_critical_mg:
                _upgrade("CRITICAL")

        # Check load overload (compare load_pct to threshold)
        if load_pct is not None:
            if load_pct > self._thresholds.load_overload_pct:
                _upgrade("OVERLOAD")

        # Check motor temperature thresholds
        if motor_temp_c is not None:
            if motor_temp_c > self._thresholds.motor_temp_warning_c:
                _upgrade("WARNING")
            if motor_temp_c > self._thresholds.motor_temp_critical_c:
                _upgrade("CRITICAL")

        return max_severity
