"""Health Score Calculator — weighted combination of anomaly confidence, rule violations, and trend."""
from typing import Optional

from elevator_pdm.domain.value_objects.health_score import HealthScore


class HealthCalculator:
    """Compute 0-100 health score.

    Weighted combination of:
    - Rule violation severity (base penalty)
    - Anomaly confidence (confidence penalty)
    - Trend direction (trend penalty)
    """

    def __init__(
        self,
        anomaly_weight: float = 0.3,
        rule_weight: float = 0.5,
        trend_weight: float = 0.2,
    ) -> None:
        self._anomaly_weight = anomaly_weight
        self._rule_weight = rule_weight
        self._trend_weight = trend_weight

    def compute(
        self,
        anomaly_confidence: float,
        rule_severity: str,  # NORMAL, WARNING, CRITICAL, OVERLOAD
        trend_direction: Optional[str] = None,  # 'up', 'down', 'stable'
        rule_confidence: float = 1.0,  # Confidence in rule violation (0.0-1.0)
    ) -> HealthScore:
        """Compute health score as weighted combination.

        Args:
            anomaly_confidence: Model confidence (0.0-1.0).
            rule_severity: Severity from rule evaluation.
            trend_direction: Trend of health scores ('up', 'down', 'stable').
            rule_confidence: Confidence in rule violation (0.0-1.0).

        Returns:
            HealthScore value object (0-100).
        """
        # Base severity penalties (percentage of 100)
        severity_penalties = {
            "NORMAL": 0.0,
            "WARNING": 50.0,
            "CRITICAL": 80.0,
            "OVERLOAD": 90.0,
        }
        base_penalty = severity_penalties.get(rule_severity, 0.0)

        # Rule impact: base penalty scaled by confidence
        rule_impact = base_penalty * rule_confidence

        # Anomaly impact: penalty for low model confidence (max 30 point penalty)
        anomaly_impact = (1.0 - anomaly_confidence) * 30.0

        # Trend impact
        trend_impact = 0.0
        if trend_direction == "down":
            trend_impact = 15.0
        elif trend_direction == "stable":
            trend_impact = 5.0
        # 'up' or None has no penalty

        # Calculate final score
        score = 100.0 - rule_impact - anomaly_impact - trend_impact

        # Clamp to 0-100 range
        score = max(0.0, min(100.0, score))

        return HealthScore(value=score)

    def compute_from_status(
        self,
        status: str,  # NORMAL, WARNING, CRITICAL, OVERLOAD
        confidence: float = 1.0,
        trend_direction: Optional[str] = None,
    ) -> HealthScore:
        """Simplified compute using just status and confidence.

        Args:
            status: Inference status (NORMAL, WARNING, CRITICAL, OVERLOAD).
            confidence: Confidence in the status.
            trend_direction: Trend direction.

        Returns:
            HealthScore value object.
        """
        # Map status to severity for scoring
        if status == "NORMAL":
            rule_severity = "NORMAL"
            rule_conf = 1.0
        elif status == "WARNING":
            rule_severity = "WARNING"
            rule_conf = confidence
        elif status in ("CRITICAL", "OVERLOAD"):
            rule_severity = "CRITICAL" if status == "CRITICAL" else "OVERLOAD"
            rule_conf = confidence
        else:
            rule_severity = "NORMAL"
            rule_conf = 1.0

        return self.compute(
            anomaly_confidence=confidence,
            rule_severity=rule_severity,
            trend_direction=trend_direction,
            rule_confidence=rule_conf,
        )
