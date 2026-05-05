"""Email notifier — sends alerts via SMTP."""
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List

from elevator_pdm.infrastructure.config.settings import Settings

logger = logging.getLogger(__name__)


class EmailNotifier:
    """Send alert notifications via SMTP email."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self._settings = settings or Settings()
        self._host = self._settings.alerts.smtp_host
        self._port = self._settings.alerts.smtp_port
        self._from = self._settings.alerts.smtp_from
        self._to = self._settings.alerts.smtp_to

    def send(
        self,
        elevator_id: str,
        severity: str,
        message: str,
        timestamp: str,
    ) -> bool:
        """Send alert notification via email.

        Args:
            elevator_id: Elevator identifier.
            severity: Alert severity (WARNING, CRITICAL, OVERLOAD).
            message: Alert message.
            timestamp: ISO timestamp of the alert.

        Returns:
            True if sent successfully, False otherwise.
        """
        if not self._host or not self._from or not self._to:
            logger.warning("SMTP not configured, skipping email notification")
            return False

        # Build email
        subject = f"[{severity}] Elevator Alert - {elevator_id}"
        body = f"""
Elevator Alert Notification

Elevator: {elevator_id}
Severity: {severity}
Time: {timestamp}

Message:
{message}

--
Elevator PDM System
"""

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self._from
        msg["To"] = ", ".join(self._to)
        msg.attach(MIMEText(body, "plain"))

        try:
            with smtplib.SMTP(self._host, self._port, timeout=5) as server:
                # If using TLS (port 587), start TLS
                if self._port == 587:
                    server.starttls()
                server.sendmail(self._from, self._to, msg.as_string())

            logger.info(f"Email notification sent for {elevator_id}: {severity}")
            return True

        except Exception as e:
            logger.error(f"Email notification error: {e}")
            return False
