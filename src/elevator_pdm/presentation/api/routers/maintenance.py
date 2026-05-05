"""Maintenance router (Task D6)."""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from elevator_pdm.presentation.api.dependencies import get_maintenance_repository, get_db_session
from elevator_pdm.domain.interfaces.maintenance_repository import MaintenanceRepository
from elevator_pdm.presentation.api.schemas.requests import MaintenanceRequest
from elevator_pdm.presentation.api.schemas.responses import MaintenanceResponse

router = APIRouter()


@router.get("/", response_model=List[MaintenanceResponse])
def list_maintenance(
    elevator_id: Optional[str] = None,
    status: Optional[str] = None,
    repo: MaintenanceRepository = Depends(get_maintenance_repository),
):
    """List maintenance records with optional filters."""
    if elevator_id:
        records = repo.find_by_elevator(elevator_id, status=status)
    else:
        # Get all records (would need a new repo method, for now return empty)
        records = []

    return [
        MaintenanceResponse(
            id=r.id,
            elevator_id=r.elevator_id,
            recommended_date=r.recommended_date,
            urgency=r.urgency,
            reason=r.reason,
            estimated_rul_hours=r.estimated_rul_hours,
            status=r.status,
            completed_at=r.completed_at,
            technician=r.technician,
            created_at=r.created_at,
        )
        for r in records
    ]


@router.post("/", response_model=MaintenanceResponse, status_code=status.HTTP_201_CREATED)
def create_maintenance(
    request: MaintenanceRequest,
    repo: MaintenanceRepository = Depends(get_maintenance_repository),
    session: Session = Depends(get_db_session),
):
    """Create a manual maintenance entry."""
    from elevator_pdm.domain.entities.maintenance import MaintenanceSchedule

    maintenance = MaintenanceSchedule(
        elevator_id=request.elevator_id,
        recommended_date=request.recommended_date,
        urgency=request.urgency,
        reason=request.reason,
    )

    repo.create(maintenance)
    session.commit()

    return MaintenanceResponse(
        id=maintenance.id if hasattr(maintenance, 'id') else None,
        elevator_id=maintenance.elevator_id,
        recommended_date=maintenance.recommended_date,
        urgency=maintenance.urgency,
        reason=maintenance.reason,
        estimated_rul_hours=maintenance.estimated_rul_hours,
        status=maintenance.status,
        created_at=maintenance.created_at,
    )


@router.patch("/{maintenance_id}", response_model=MaintenanceResponse)
def update_maintenance(
    maintenance_id: int,
    status: Optional[str] = None,
    completed_at: Optional[str] = None,
    technician: Optional[str] = None,
    repo: MaintenanceRepository = Depends(get_maintenance_repository),
    session: Session = Depends(get_db_session),
):
    """Update maintenance status."""
    # Cannot transition completed -> pending
    records = repo.find_by_elevator("")
    record = next((r for r in records if r.id == maintenance_id), None)

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Maintenance {maintenance_id} not found",
        )

    if record.status == "completed" and status == "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot transition completed -> pending",
        )

    kwargs = {}
    if status:
        kwargs["status"] = status
    if completed_at:
        kwargs["completed_at"] = completed_at
    if technician:
        kwargs["technician"] = technician

    repo.update_status(maintenance_id, status or record.status, **kwargs)
    session.commit()

    record.status = status or record.status

    return MaintenanceResponse(
        id=record.id,
        elevator_id=record.elevator_id,
        recommended_date=record.recommended_date,
        urgency=record.urgency,
        reason=record.reason,
        estimated_rul_hours=record.estimated_rul_hours,
        status=record.status,
        completed_at=record.completed_at,
        technician=record.technician,
        created_at=record.created_at,
    )
