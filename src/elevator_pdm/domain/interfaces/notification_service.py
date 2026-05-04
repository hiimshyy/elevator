"""Notification service interface (port)."""
from abc import ABC, abstractmethod

from elevator_pdm.domain.entities.alert import Alert


class NotificationService(ABC):
    """Abstract interface for dispatching alert notifications.

    Infrastructure layer provides concrete implementations:
    - SlackNotifier: Slack webhook
    - EmailNotifier: SMTP
    - CompositeNotifier: fan-out to multiple channels
    """

    @abstractmethod
    def send_alert(self, alert: Alert) -> bool:
        """Send an alert notification.

        Args:
            alert: The alert to dispatch

        Returns:
            True if sent successfully, False otherwise
        """
        ...
