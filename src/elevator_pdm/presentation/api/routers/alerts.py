"""Alerts router (Task D5)."""

from fastapi import APIRouter, Depends, HTTPException, status

from elevator_pdm.domain.interfaces.alert_repository import AlertRepository
from elevator_pdm.presentation.api.dependencies import get_alert_repository
from elevator_pdm.presentation.api.schemas.requests import AlertAcknowledgeRequest
from elevator_pdm.presentation.api.schemas.responses import AlertResponse

router = APIRouter()


@router.get("/", response_model=list[AlertResponse])
def list_alerts(
    elevator_id: str | None = None,
    severity: str | None = None,
    acknowledged: bool | None = None,
    repo: AlertRepository = Depends(get_alert_repository),
):
    """List alerts with optional filters."""
    if elevator_id:
        alerts = repo.find_by_elevator(elevator_id, severity=severity, acknowledged=acknowledged)
    else:
        alerts = repo.find_all(severity=severity, acknowledged=acknowledged)

    return [
        AlertResponse(
            id=a.id,
            elevator_id=a.elevator_id,
            timestamp=a.sent_at,
            severity=a.severity,
            message=a.message,
            acknowledged=1 if a.acknowledged else 0,
            acknowledged_by=a.acknowledged_by,
            acknowledged_at=a.acknowledged_at,
        )
        for a in alerts
    ]


@router.patch("/{alert_id}/acknowledge", response_model=AlertResponse)
def acknowledge_alert(
    alert_id: int,
    request: AlertAcknowledgeRequest,
    repo: AlertRepository = Depends(get_alert_repository),
):
    """Acknowledge an alert."""
    alert = repo.get_by_id(alert_id)
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert {alert_id} not found",
        )

    repo.acknowledge(alert_id=alert_id, acknowledged_by=request.technician)
    updated = repo.get_by_id(alert_id)
    assert updated is not None

    return AlertResponse(
        id=updated.id,
        elevator_id=updated.elevator_id,
        timestamp=updated.sent_at,
        severity=updated.severity,
        message=updated.message,
        acknowledged=1 if updated.acknowledged else 0,
        acknowledged_by=updated.acknowledged_by,
        acknowledged_at=updated.acknowledged_at,
    )
