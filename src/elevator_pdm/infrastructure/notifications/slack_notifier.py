"""Slack notifier — sends alerts via webhook."""
import json
import logging
from typing import Optional

import requests
from requests.exceptions import RequestException

from elevator_pdm.infrastructure.config.settings import Settings

logger = logging.getLogger(__name__)


class SlackNotifier:
    """Send alert notifications to Slack via webhook."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self._settings = settings or Settings()
        self._webhook_url = self._settings.alerts.slack_webhook

    def send(
        self,
        elevator_id: str,
        severity: str,
        message: str,
        timestamp: str,
    ) -> bool:
        """Send alert notification to Slack.

        Args:
            elevator_id: Elevator identifier.
            severity: Alert severity (WARNING, CRITICAL, OVERLOAD).
            message: Alert message.
            timestamp: ISO timestamp of the alert.

        Returns:
            True if sent successfully, False otherwise.
        """
        if not self._webhook_url:
            logger.warning("Slack webhook URL not configured, skipping notification")
            return False

        # Format message for Slack
        color_map = {
            "WARNING": "#ffcc00",
            "CRITICAL": "#ff0000",
            "OVERLOAD": "#ff0000",
        }
        color = color_map.get(severity, "#36a64f")

        payload = {
            "attachments": [
                {
                    "color": color,
                    "fields": [
                        {"title": "Elevator", "value": elevator_id, "short": True},
                        {"title": "Severity", "value": severity, "short": True},
                        {"title": "Time", "value": timestamp, "short": True},
                        {"title": "Message", "value": message, "short": False},
                    ],
                }
            ]
        }

        try:
            response = requests.post(
                self._webhook_url,
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
                timeout=5,
            )
            if response.status_code == 200 and response.text == "ok":
                logger.info(f"Slack notification sent for {elevator_id}: {severity}")
                return True
            else:
                logger.error(
                    f"Slack notification failed: {response.status_code} - {response.text}"
                )
                return False
        except Exception as e:
            logger.error(f"Slack notification error: {e}")
            return False
