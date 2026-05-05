"""Composite notifier — fans out to multiple notification channels."""
import logging
from typing import List, Optional

from elevator_pdm.infrastructure.config.settings import Settings

logger = logging.getLogger(__name__)


class CompositeNotifier:
    """Send notifications via multiple channels (Slack, Email)."""

    def __init__(
        self,
        slack_notifier: Optional[object] = None,
        email_notifier: Optional[object] = None,
        settings: Optional[Settings] = None,
    ) -> None:
        self._notifiers = []

        # Lazy-initialize Slack notifier
        if slack_notifier:
            self._notifiers.append(("Slack", slack_notifier))
        elif settings and settings.alerts.slack_webhook:
            from elevator_pdm.infrastructure.notifications.slack_notifier import SlackNotifier

            self._notifiers.append(("Slack", SlackNotifier(settings)))

        # Lazy-initialize Email notifier
        if email_notifier:
            self._notifiers.append(("Email", email_notifier))
        elif settings and settings.alerts.smtp_host:
            from elevator_pdm.infrastructure.notifications.email_notifier import EmailNotifier

            self._notifiers.append(("Email", EmailNotifier(settings)))

    def send(
        self,
        elevator_id: str,
        severity: str,
        message: str,
        timestamp: str,
    ) -> dict[str, bool]:
        """Send notification via all configured channels.

        Args:
            elevator_id: Elevator identifier.
            severity: Alert severity.
            message: Alert message.
            timestamp: ISO timestamp.

        Returns:
            Dict mapping channel name to success status.
        """
        results = {}

        for name, notifier in self._notifiers:
            try:
                success = notifier.send(elevator_id, severity, message, timestamp)
                results[name] = success
            except Exception as e:
                logger.error(f"{name} notification error: {e}")
                results[name] = False

        return results

    def is_configured(self) -> bool:
        """Check if any notification channel is configured."""
        return len(self._notifiers) > 0

    def active_channels(self) -> List[str]:
        """Return list of active notification channels."""
        return [name for name, _ in self._notifiers]
