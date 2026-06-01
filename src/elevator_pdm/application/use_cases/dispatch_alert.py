"""Dispatch alert use case with rate limiting."""
import logging
import time
from collections import defaultdict

from elevator_pdm.domain.entities.alert import Alert
from elevator_pdm.domain.interfaces.alert_repository import AlertRepository
from elevator_pdm.infrastructure.config.settings import Settings

logger = logging.getLogger(__name__)

RATE_LIMIT_SECONDS = 15 * 60


class DispatchAlert:
    """Dispatch alerts and suppress duplicates within the rate-limit window."""

    def __init__(
        self,
        alert_repo: AlertRepository,
        notifier: object | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._alert_repo = alert_repo
        self._notifier = notifier
        self._settings = settings or Settings()
        self._rate_limit_cache: dict[str, dict[str, float]] = defaultdict(dict)
        self._init_rate_limit_cache()

    def _init_rate_limit_cache(self) -> None:
        """Initialize any rate-limit state."""
        # This implementation currently relies on in-memory state only.

    def execute(
        self,
        elevator_id: str,
        severity: str,
        message: str,
        timestamp: str,
        *,
        inference_id: int = 0,
        alert_type: str | None = None,
        channel: str = "slack",
    ) -> tuple[bool, str]:
        """Dispatch an alert unless the same alert type is still rate-limited."""
        current_time = time.time()
        normalized_severity, normalized_alert_type = self._normalize_alert(severity, alert_type)
        rate_limit_key = alert_type or severity

        if self._is_rate_limited(elevator_id, rate_limit_key, current_time):
            logger.info(
                "Alert suppressed for %s (%s) - rate limit: 1 per %s min",
                elevator_id,
                rate_limit_key,
                self._settings.alerts.rate_limit_minutes,
            )
            return False, "rate_limited"

        alert = Alert(
            elevator_id=elevator_id,
            inference_id=inference_id,
            alert_type=normalized_alert_type,
            severity=normalized_severity,
            message=message,
            sent_at=timestamp,
            channel=channel,
        )
        self._alert_repo.save(alert)
        self._rate_limit_cache[elevator_id][rate_limit_key] = current_time

        if self._notifier and self._notifier.is_configured():
            notified = self._notifier.send(
                elevator_id=elevator_id,
                severity=normalized_severity,
                message=message,
                timestamp=timestamp,
            )
            logger.info("Notifications sent: %s", notified)

        return True, "dispatched"

    def _is_rate_limited(
        self,
        elevator_id: str,
        alert_key: str,
        current_time: float,
    ) -> bool:
        if elevator_id not in self._rate_limit_cache:
            return False
        if alert_key not in self._rate_limit_cache[elevator_id]:
            return False

        last_sent = self._rate_limit_cache[elevator_id][alert_key]
        return (current_time - last_sent) < RATE_LIMIT_SECONDS

    def _normalize_alert(self, severity: str, alert_type: str | None) -> tuple[str, str]:
        if severity == "OVERLOAD":
            return "EMERGENCY", alert_type or "OVERLOAD"

        if severity not in {"WARNING", "CRITICAL", "EMERGENCY"}:
            raise ValueError(f"Unsupported alert severity: {severity}")

        default_alert_type = {
            "WARNING": "HEALTH_LOW",
            "CRITICAL": "HEALTH_LOW",
            "EMERGENCY": "OVERLOAD",
        }
        return severity, alert_type or default_alert_type[severity]

    def clear_rate_limit_cache(self) -> None:
        """Clear the rate limit cache."""
        self._rate_limit_cache.clear()
