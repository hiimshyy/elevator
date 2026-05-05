"""Dispatch alert use case with rate limiting."""
import logging
import time
from typing import Optional, Dict, List, Tuple
from collections import defaultdict

from elevator_pdm.domain.entities.alert import Alert
from elevator_pdm.domain.interfaces.alert_repository import AlertRepository
from elevator_pdm.infrastructure.config.settings import Settings

logger = logging.getLogger(__name__)

# Rate limit: 15 minutes in seconds
RATE_LIMIT_SECONDS = 15 * 60


class DispatchAlert:
    """Dispatch alert with rate limiting (1 per 15 min per elevator per alert type)."""

    def __init__(
        self,
        alert_repo: AlertRepository,
        notifier: Optional[object] = None,
        settings: Optional[Settings] = None,
    ) -> None:
        self._alert_repo = alert_repo
        self._notifier = notifier
        self._settings = settings or Settings()

        # Rate limiting: {elevator_id: {severity: last_sent_timestamp}}
        self._rate_limit_cache: Dict[str, Dict[str, float]] = defaultdict(dict)

        # Load recent alerts to initialize cache
        self._init_rate_limit_cache()

    def _init_rate_limit_cache(self) -> None:
        """Initialize rate limit cache from recent alerts."""
        # Get recent alerts within rate limit window
        cutoff = time.time() - RATE_LIMIT_SECONDS

        # This is a simplified approach — in production, query DB for recent alerts
        # For now, we'll rely on in-memory cache only

    def execute(
        self,
        elevator_id: str,
        severity: str,
        message: str,
        timestamp: str,
    ) -> Tuple[bool, str]:
        """Dispatch alert with rate limiting.

        Args:
            elevator_id: Elevator identifier.
            severity: Alert severity (WARNING, CRITICAL, OVERLOAD).
            message: Alert message.
            timestamp: ISO timestamp.

        Returns:
            Tuple of (dispatched, reason).
            dispatched: True if alert was dispatched.
            reason: Reason for suppression or success.
        """
        current_time = time.time()

        # Check rate limit
        if self._is_rate_limited(elevator_id, severity, current_time):
            logger.info(
                f"Alert suppressed for {elevator_id} ({severity}) - "
                f"rate limit: 1 per {self._settings.alerts.rate_limit_minutes} min"
            )
            return False, "rate_limited"

        # Create alert record
        alert = Alert(
            elevator_id=elevator_id,
            inference_id=0,  # Placeholder - would be linked to actual inference
            alert_type=severity,  # Use severity as alert_type
            severity=severity,
            message=message,
            sent_at=timestamp,
            channel="slack",  # Default channel
        )
        self._alert_repo.create(alert)

        # Update rate limit cache
        self._rate_limit_cache[elevator_id][severity] = current_time

        # Send notifications
        notified = {}
        if self._notifier and self._notifier.is_configured():
            notified = self._notifier.send(
                elevator_id=elevator_id,
                severity=severity,
                message=message,
                timestamp=timestamp,
            )
            logger.info(f"Notifications sent: {notified}")

        return True, "dispatched"

    def _is_rate_limited(
        self,
        elevator_id: str,
        severity: str,
        current_time: float,
    ) -> bool:
        """Check if alert is rate limited.

        Args:
            elevator_id: Elevator identifier.
            severity: Alert severity.
            current_time: Current timestamp.

        Returns:
            True if rate limited (should suppress), False otherwise.
        """
        if elevator_id not in self._rate_limit_cache:
            return False

        if severity not in self._rate_limit_cache[elevator_id]:
            return False

        last_sent = self._rate_limit_cache[elevator_id][severity]
        elapsed = current_time - last_sent

        # Different alert types are not suppressed
        return elapsed < RATE_LIMIT_SECONDS

    def clear_rate_limit_cache(self) -> None:
        """Clear the rate limit cache (for testing)."""
        self._rate_limit_cache.clear()
