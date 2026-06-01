"""SQLite implementation of MaintenanceRepository."""

from sqlalchemy.orm import Session

from elevator_pdm.domain.entities.maintenance import MaintenanceSchedule
from elevator_pdm.domain.interfaces.maintenance_repository import MaintenanceRepository
from elevator_pdm.infrastructure.persistence.models import MaintenanceSchedule as ORMaintenance


class SQLiteMaintenanceRepo(MaintenanceRepository):
    """SQLite adapter for MaintenanceRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def _to_orm(self, maintenance: MaintenanceSchedule) -> ORMaintenance:
        """Convert domain entity to ORM model."""
        return ORMaintenance(
            elevator_id=maintenance.elevator_id,
            recommended_date=maintenance.recommended_date,
            urgency=maintenance.urgency,
            reason=maintenance.reason,
            estimated_rul_hours=maintenance.estimated_rul_hours,
            status=maintenance.status,
            completed_at=maintenance.completed_at,
            technician=maintenance.technician,
            created_at=maintenance.created_at,
        )

    def _to_domain(self, orm_maint: ORMaintenance) -> MaintenanceSchedule:
        """Convert ORM model to domain entity."""
        return MaintenanceSchedule(
            id=orm_maint.id,
            elevator_id=orm_maint.elevator_id,
            recommended_date=orm_maint.recommended_date,
            urgency=orm_maint.urgency,
            reason=orm_maint.reason,
            estimated_rul_hours=orm_maint.estimated_rul_hours,
            status=orm_maint.status,
            completed_at=orm_maint.completed_at,
            technician=orm_maint.technician,
            created_at=orm_maint.created_at,
        )

    def create(self, maintenance: MaintenanceSchedule) -> None:
        """Create a maintenance schedule entry."""
        orm_maint = self._to_orm(maintenance)
        self._session.add(orm_maint)
        self._session.commit()
        self._session.refresh(orm_maint)
        maintenance.id = orm_maint.id
        maintenance.created_at = orm_maint.created_at

    def find_by_elevator(
        self,
        elevator_id: str,
        status: str | None = None,
    ) -> list[MaintenanceSchedule]:
        """Query maintenance records for an elevator with optional status filter."""
        query = self._session.query(ORMaintenance).filter_by(elevator_id=elevator_id)

        return self._run_filtered_query(query, status=status)

    def find_all(self, status: str | None = None) -> list[MaintenanceSchedule]:
        """Query maintenance records across all elevators."""
        query = self._session.query(ORMaintenance)
        return self._run_filtered_query(query, status=status)

    def get_by_id(self, maintenance_id: int) -> MaintenanceSchedule | None:
        """Get a single maintenance record by database ID."""
        orm_maint = self._session.query(ORMaintenance).filter_by(id=maintenance_id).first()
        return self._to_domain(orm_maint) if orm_maint else None

    def _run_filtered_query(self, query, status: str | None = None) -> list[MaintenanceSchedule]:
        """Apply common maintenance filters and return domain entities."""
        if status:
            query = query.filter_by(status=status)

        query = query.order_by(ORMaintenance.created_at.desc())
        return [self._to_domain(m) for m in query.all()]

    def update_status(self, maintenance_id: int, status: str, **kwargs) -> None:
        """Update maintenance status and optional fields."""
        orm_maint = self._session.query(ORMaintenance).filter_by(id=maintenance_id).first()
        if orm_maint:
            orm_maint.status = status
            # Update optional fields
            if "completed_at" in kwargs:
                orm_maint.completed_at = kwargs["completed_at"]
            if "technician" in kwargs:
                orm_maint.technician = kwargs["technician"]
            self._session.commit()
