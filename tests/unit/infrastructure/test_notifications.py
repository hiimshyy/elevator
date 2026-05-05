"""Tests for notification services."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

from elevator_pdm.infrastructure.notifications.slack_notifier import SlackNotifier
from elevator_pdm.infrastructure.notifications.email_notifier import EmailNotifier
from elevator_pdm.infrastructure.notifications.composite_notifier import CompositeNotifier
from elevator_pdm.application.use_cases.dispatch_alert import DispatchAlert
from elevator_pdm.domain.interfaces.alert_repository import AlertRepository
from elevator_pdm.infrastructure.config.settings import Settings


class MockAlertRepository:
    """Mock alert repository for testing."""

    def __init__(self):
        self.alerts = []

    def create(self, alert):
        self.alerts.append(alert)

    def find_by_elevator(self, elevator_id, severity=None):
        return [a for a in self.alerts if a.elevator_id == elevator_id]

    def acknowledge(self, alert_id, technician, timestamp):
        pass


class TestSlackNotifier:
    """Tests for SlackNotifier."""

    def setup_method(self):
        self.settings = Settings()
        self.settings.alerts.slack_webhook = "https://hooks.slack.com/test"
        self.notifier = SlackNotifier(settings=self.settings)

    @patch("elevator_pdm.infrastructure.notifications.slack_notifier.requests.post")
    def test_sends_post_to_webhook_url(self, mock_post):
        """① Slack notifier sends POST to webhook URL."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "ok"
        mock_post.return_value = mock_response

        result = self.notifier.send(
            elevator_id="elev-001",
            severity="WARNING",
            message="High vibration detected",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        assert result is True
        mock_post.assert_called_once()
        # Verify the URL
        call_args = mock_post.call_args
        assert call_args[0][0] == "https://hooks.slack.com/test"

    @patch("elevator_pdm.infrastructure.notifications.slack_notifier.requests.post")
    def test_returns_false_on_failure(self, mock_post):
        """Slack returns non-200."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_post.return_value = mock_response

        result = self.notifier.send(
            elevator_id="elev-001",
            severity="CRITICAL",
            message="Test",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        assert result is False

    @patch("elevator_pdm.infrastructure.notifications.slack_notifier.requests.post")
    def test_returns_false_on_exception(self, mock_post):
        """Slack raises exception."""
        mock_post.side_effect = Exception("Connection error")

        result = self.notifier.send(
            elevator_id="elev-001",
            severity="WARNING",
            message="Test",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        assert result is False

    def test_skips_when_webhook_not_configured(self, caplog):
        """Slack webhook not configured."""
        settings = Settings()
        settings.alerts.slack_webhook = ""
        notifier = SlackNotifier(settings=settings)

        result = notifier.send(
            elevator_id="elev-001",
            severity="WARNING",
            message="Test",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        assert result is False


class TestEmailNotifier:
    """Tests for EmailNotifier."""

    def setup_method(self):
        self.settings = Settings()
        self.settings.alerts.smtp_host = "smtp.gmail.com"
        self.settings.alerts.smtp_port = 587
        self.settings.alerts.smtp_from = "alerts@example.com"
        self.settings.alerts.smtp_to = ["admin@example.com"]

    @patch("elevator_pdm.infrastructure.notifications.email_notifier.smtplib.SMTP")
    def test_sends_via_smtp(self, mock_smtp_class):
        """② Email notifier sends via SMTP."""
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__ = Mock(return_value=mock_server)
        mock_smtp_class.return_value.__exit__ = Mock(return_value=False)

        notifier = EmailNotifier(settings=self.settings)
        result = notifier.send(
            elevator_id="elev-001",
            severity="CRITICAL",
            message="Motor overheating",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        assert result is True
        # Verify SMTP was used
        mock_smtp_class.assert_called_once_with("smtp.gmail.com", 587, timeout=5)
        # Verify sendmail was called
        mock_server.sendmail.assert_called_once()

    @patch("elevator_pdm.infrastructure.notifications.email_notifier.smtplib.SMTP")
    def test_returns_false_on_exception(self, mock_smtp_class):
        """SMTP raises exception."""
        mock_smtp_class.side_effect = Exception("SMTP error")

        notifier = EmailNotifier(settings=self.settings)
        result = notifier.send(
            elevator_id="elev-001",
            severity="WARNING",
            message="Test",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        assert result is False

    def test_skips_when_not_configured(self, caplog):
        """SMTP not configured."""
        settings = Settings()
        settings.alerts.smtp_host = ""
        notifier = EmailNotifier(settings=settings)

        result = notifier.send(
            elevator_id="elev-001",
            severity="WARNING",
            message="Test",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        assert result is False


class TestCompositeNotifier:
    """Tests for CompositeNotifier."""

    def test_calls_both_channels(self):
        """③ Composite calls both Slack and Email."""
        mock_slack = Mock()
        mock_slack.send.return_value = True
        mock_email = Mock()
        mock_email.send.return_value = True

        composite = CompositeNotifier(
            slack_notifier=mock_slack,
            email_notifier=mock_email,
        )

        results = composite.send(
            elevator_id="elev-001",
            severity="WARNING",
            message="Test",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        mock_slack.send.assert_called_once()
        mock_email.send.assert_called_once()
        assert results["Slack"] is True
        assert results["Email"] is True

    def test_handles_partial_failure(self):
        """One channel fails, other succeeds."""
        mock_slack = Mock()
        mock_slack.send.return_value = False
        mock_email = Mock()
        mock_email.send.return_value = True

        composite = CompositeNotifier(
            slack_notifier=mock_slack,
            email_notifier=mock_email,
        )

        results = composite.send(
            elevator_id="elev-001",
            severity="WARNING",
            message="Test",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        assert results["Slack"] is False
        assert results["Email"] is True

    def test_is_configured_false_when_empty(self):
        """No channels configured."""
        composite = CompositeNotifier()
        assert composite.is_configured() is False

    def test_active_channels(self):
        """Returns list of active channels."""
        mock_slack = Mock()
        composite = CompositeNotifier(slack_notifier=mock_slack)
        assert composite.active_channels() == ["Slack"]


class TestDispatchAlert:
    """Tests for DispatchAlert use case."""

    def setup_method(self):
        self.repo = MockAlertRepository()
        self.mock_notifier = Mock()
        self.mock_notifier.is_configured.return_value = True
        self.mock_notifier.send.return_value = {"Slack": True}

        self.dispatcher = DispatchAlert(
            alert_repo=self.repo,
            notifier=self.mock_notifier,
        )

    def test_dispatches_alert(self):
        """Alert is dispatched and recorded."""
        dispatched, reason = self.dispatcher.execute(
            elevator_id="elev-001",
            severity="WARNING",
            message="High vibration",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        assert dispatched is True
        assert reason == "dispatched"
        assert len(self.repo.alerts) == 1
        assert self.repo.alerts[0].severity == "WARNING"

    def test_rate_limiter_suppresses_duplicate_alerts(self):
        """④ Rate limiter suppresses duplicate alerts within 15 min."""
        timestamp = datetime.now(timezone.utc).isoformat()

        # First alert - should dispatch
        dispatched1, _ = self.dispatcher.execute(
            elevator_id="elev-001",
            severity="WARNING",
            message="Alert 1",
            timestamp=timestamp,
        )
        assert dispatched1 is True

        # Second identical alert within rate limit - should be suppressed
        dispatched2, reason = self.dispatcher.execute(
            elevator_id="elev-001",
            severity="WARNING",
            message="Alert 2",
            timestamp=timestamp,
        )
        assert dispatched2 is False
        assert reason == "rate_limited"

    def test_different_alert_types_not_suppressed(self):
        """⑤ Different alert types are not suppressed."""
        timestamp = datetime.now(timezone.utc).isoformat()

        # First alert - WARNING
        dispatched1, _ = self.dispatcher.execute(
            elevator_id="elev-001",
            severity="WARNING",
            message="Warning alert",
            timestamp=timestamp,
        )
        assert dispatched1 is True

        # Different severity - should NOT be suppressed
        dispatched2, reason = self.dispatcher.execute(
            elevator_id="elev-001",
            severity="CRITICAL",
            message="Critical alert",
            timestamp=timestamp,
        )
        assert dispatched2 is True
        assert reason == "dispatched"

    def test_different_elevators_not_suppressed(self):
        """Different elevators are not suppressed."""
        timestamp = datetime.now(timezone.utc).isoformat()

        # First elevator
        dispatched1, _ = self.dispatcher.execute(
            elevator_id="elev-001",
            severity="WARNING",
            message="Alert 1",
            timestamp=timestamp,
        )
        assert dispatched1 is True

        # Different elevator - should NOT be suppressed
        dispatched2, reason = self.dispatcher.execute(
            elevator_id="elev-002",
            severity="WARNING",
            message="Alert 2",
            timestamp=timestamp,
        )
        assert dispatched2 is True

    def test_clears_rate_limit_cache(self):
        """Clear cache works."""
        timestamp = datetime.now(timezone.utc).isoformat()

        # Dispatch an alert
        self.dispatcher.execute(
            elevator_id="elev-001",
            severity="WARNING",
            message="Alert",
            timestamp=timestamp,
        )

        # Clear cache
        self.dispatcher.clear_rate_limit_cache()

        # Should be able to dispatch again
        dispatched, _ = self.dispatcher.execute(
            elevator_id="elev-001",
            severity="WARNING",
            message="Alert after clear",
            timestamp=timestamp,
        )
        assert dispatched is True
