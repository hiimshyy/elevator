"""SQLite implementation of AlertRepository."""
from typing import List, Optional
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from elevator_pdm.domain.interfaces.alert_repository import AlertRepository
from elevator_pdm.domain.entities.alert import Alert
from elevator_pdm.infrastructure.persistence.models import Alert as ORMAlert


class SQLiteAlertRepo(AlertRepository):
    """SQLite adapter for AlertRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def _to_orm(self, alert: Alert) -> ORMAlert:
        """Convert domain entity to ORM model."""
        return ORMAlert(
            elevator_id=alert.elevator_id,
            inference_id=alert.inference_id,
            alert_type=alert.alert_type,
            severity=alert.severity,
            message=alert.message,
            sent_at=alert.sent_at,
            channel=alert.channel,
            acknowledged=1 if alert.acknowledged else 0,
            acknowledged_by=alert.acknowledged_by,
            acknowledged_at=alert.acknowledged_at,
        )

    def _to_domain(self, orm_alert: ORMAlert) -> Alert:
        """Convert ORM model to domain entity."""
        return Alert(
            elevator_id=orm_alert.elevator_id,
            inference_id=orm_alert.inference_id,
            alert_type=orm_alert.alert_type,
            severity=orm_alert.severity,
            message=orm_alert.message,
            sent_at=orm_alert.sent_at,
            channel=orm_alert.channel,
            acknowledged=bool(orm_alert.acknowledged),
            acknowledged_by=orm_alert.acknowledged_by,
            acknowledged_at=orm_alert.acknowledged_at,
        )

    def save(self, alert: Alert) -> None:
        """Save an alert."""
        orm_alert = self._to_orm(alert)
        self._session.add(orm_alert)
        self._session.commit()

    def find_by_elevator(
        self,
        elevator_id: str,
        severity: Optional[str] = None,
        acknowledged: Optional[bool] = None,
    ) -> List[Alert]:
        """Query alerts for an elevator with optional filters."""
        query = self._session.query(ORMAlert).filter_by(elevator_id=elevator_id)

        if severity:
            query = query.filter_by(severity=severity)
        if acknowledged is not None:
            query = query.filter_by(acknowledged=1 if acknowledged else 0)

        query = query.order_by(ORMAlert.sent_at.desc())
        return [self._to_domain(a) for a in query.all()]

    def acknowledge(self, alert_id: int, acknowledged_by: str) -> None:
        """Mark an alert as acknowledged."""
        orm_alert = self._session.query(ORMAlert).filter_by(id=alert_id).first()
        if orm_alert:
            orm_alert.acknowledged = 1
            orm_alert.acknowledged_by = acknowledged_by
            orm_alert.acknowledged_at = datetime.now(timezone.utc).isoformat()
            self._session.commit()
