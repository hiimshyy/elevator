"""Regression tests for alerts and maintenance API routers."""

from fastapi import HTTPException

from elevator_pdm.domain.entities.alert import Alert
from elevator_pdm.domain.entities.maintenance import MaintenanceSchedule
from elevator_pdm.presentation.api.routers.alerts import acknowledge_alert, list_alerts
from elevator_pdm.presentation.api.routers.maintenance import (
    create_maintenance,
    list_maintenance,
    update_maintenance,
)
from elevator_pdm.presentation.api.schemas.requests import (
    AlertAcknowledgeRequest,
    MaintenanceRequest,
)


class _FakeAlertRepo:
    def __init__(self) -> None:
        self.alerts = [
            Alert(
                id=1,
                elevator_id="elev-001",
                inference_id=1,
                alert_type="VIBRATION_HIGH",
                severity="WARNING",
                message="High vibration detected",
                sent_at="2026-06-01T00:00:00+00:00",
                channel="slack",
                acknowledged=False,
            )
        ]
        self.acknowledged_calls: list[tuple[int, str]] = []

    def save(self, alert: Alert) -> None:
        self.alerts.append(alert)

    def find_by_elevator(
        self,
        elevator_id: str,
        severity: str | None = None,
        acknowledged: bool | None = None,
    ) -> list[Alert]:
        return [
            alert
            for alert in self.find_all(severity=severity, acknowledged=acknowledged)
            if alert.elevator_id == elevator_id
        ]

    def find_all(
        self,
        severity: str | None = None,
        acknowledged: bool | None = None,
    ) -> list[Alert]:
        alerts = self.alerts
        if severity:
            alerts = [alert for alert in alerts if alert.severity == severity]
        if acknowledged is not None:
            alerts = [alert for alert in alerts if alert.acknowledged is acknowledged]
        return alerts

    def get_by_id(self, alert_id: int) -> Alert | None:
        return next((alert for alert in self.alerts if alert.id == alert_id), None)

    def acknowledge(self, alert_id: int, acknowledged_by: str) -> None:
        self.acknowledged_calls.append((alert_id, acknowledged_by))
        alert = self.get_by_id(alert_id)
        assert alert is not None
        alert.acknowledged = True
        alert.acknowledged_by = acknowledged_by
        alert.acknowledged_at = "2026-06-01T01:00:00+00:00"


class _FakeMaintenanceRepo:
    def __init__(self) -> None:
        self.records = [
            MaintenanceSchedule(
                id=1,
                elevator_id="elev-001",
                recommended_date="2026-06-10",
                urgency="soon",
                reason="Monitor vibration trend",
                status="pending",
                created_at="2026-06-01T00:00:00+00:00",
            )
        ]

    def create(self, maintenance: MaintenanceSchedule) -> None:
        maintenance.id = len(self.records) + 1
        self.records.append(maintenance)

    def find_by_elevator(
        self,
        elevator_id: str,
        status: str | None = None,
    ) -> list[MaintenanceSchedule]:
        return [
            record
            for record in self.find_all(status=status)
            if record.elevator_id == elevator_id
        ]

    def find_all(self, status: str | None = None) -> list[MaintenanceSchedule]:
        records = self.records
        if status:
            records = [record for record in records if record.status == status]
        return records

    def get_by_id(self, maintenance_id: int) -> MaintenanceSchedule | None:
        return next((record for record in self.records if record.id == maintenance_id), None)

    def update_status(self, maintenance_id: int, status: str, **kwargs) -> None:
        record = self.get_by_id(maintenance_id)
        assert record is not None
        record.status = status
        if "completed_at" in kwargs:
            record.completed_at = kwargs["completed_at"]
        if "technician" in kwargs:
            record.technician = kwargs["technician"]


def test_list_alerts_returns_all_alerts_when_elevator_not_filtered() -> None:
    repo = _FakeAlertRepo()

    result = list_alerts(repo=repo)

    assert len(result) == 1
    assert result[0].id == 1


def test_acknowledge_alert_updates_record() -> None:
    repo = _FakeAlertRepo()

    result = acknowledge_alert(
        alert_id=1,
        request=AlertAcknowledgeRequest(technician="tech-01"),
        repo=repo,
    )

    assert result.acknowledged == 1
    assert result.acknowledged_by == "tech-01"
    assert repo.acknowledged_calls == [(1, "tech-01")]


def test_list_maintenance_returns_all_records() -> None:
    repo = _FakeMaintenanceRepo()

    result = list_maintenance(repo=repo)

    assert len(result) == 1
    assert result[0].id == 1


def test_create_maintenance_returns_created_record() -> None:
    repo = _FakeMaintenanceRepo()

    result = create_maintenance(
        request=MaintenanceRequest(
            elevator_id="elev-001",
            recommended_date="2026-06-15",
            urgency="urgent",
            reason="Manual inspection",
        ),
        repo=repo,
    )

    assert result.id == 2
    assert result.urgency == "urgent"


def test_update_maintenance_rejects_completed_to_pending_transition() -> None:
    repo = _FakeMaintenanceRepo()
    record = repo.get_by_id(1)
    assert record is not None
    record.status = "completed"

    try:
        update_maintenance(
            maintenance_id=1,
            status="pending",
            repo=repo,
        )
    except HTTPException as exc:
        assert exc.status_code == 400
    else:
        raise AssertionError("Expected HTTPException")
