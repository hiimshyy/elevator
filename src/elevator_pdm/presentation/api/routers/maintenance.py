"""Maintenance router (Task D6)."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status

from elevator_pdm.domain.interfaces.maintenance_repository import MaintenanceRepository
from elevator_pdm.presentation.api.dependencies import get_maintenance_repository
from elevator_pdm.presentation.api.schemas.requests import MaintenanceRequest
from elevator_pdm.presentation.api.schemas.responses import MaintenanceResponse

router = APIRouter()


def _to_response(record) -> MaintenanceResponse:
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


@router.get("/", response_model=list[MaintenanceResponse])
def list_maintenance(
    elevator_id: str | None = None,
    status: str | None = None,
    repo: MaintenanceRepository = Depends(get_maintenance_repository),
):
    """List maintenance records with optional filters."""
    if elevator_id:
        records = repo.find_by_elevator(elevator_id, status=status)
    else:
        records = repo.find_all(status=status)

    return [_to_response(record) for record in records]


@router.post(
    "/",
    response_model=MaintenanceResponse,
    status_code=http_status.HTTP_201_CREATED,
)
def create_maintenance(
    request: MaintenanceRequest,
    repo: MaintenanceRepository = Depends(get_maintenance_repository),
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

    if maintenance.id is None:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Maintenance record was created without an ID",
        )

    created = repo.get_by_id(maintenance.id)
    if not created:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Maintenance {maintenance.id} could not be reloaded after creation",
        )

    return _to_response(created)


@router.patch("/{maintenance_id}", response_model=MaintenanceResponse)
def update_maintenance(
    maintenance_id: int,
    status: str | None = None,
    completed_at: str | None = None,
    technician: str | None = None,
    repo: MaintenanceRepository = Depends(get_maintenance_repository),
):
    """Update maintenance status."""
    record = repo.get_by_id(maintenance_id)
    if not record:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Maintenance {maintenance_id} not found",
        )

    if record.status == "completed" and status == "pending":
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
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
    updated = repo.get_by_id(maintenance_id)
    assert updated is not None

    return _to_response(updated)
