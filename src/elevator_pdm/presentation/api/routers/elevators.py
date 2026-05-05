"""Elevator & Readings routers (Task D3)."""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from elevator_pdm.presentation.api.dependencies import (
    get_elevator_repository,
    get_reading_repository,
    get_inference_repository,
)
from elevator_pdm.domain.interfaces.elevator_repository import ElevatorRepository
from elevator_pdm.domain.interfaces.reading_repository import ReadingRepository
from elevator_pdm.domain.interfaces.inference_repository import InferenceRepository
from elevator_pdm.presentation.api.schemas.responses import (
    ElevatorResponse,
    SensorReadingResponse,
    InferenceResponse,
)

router = APIRouter()


@router.get("/", response_model=List[ElevatorResponse])
def list_elevators(
    repo: ElevatorRepository = Depends(get_elevator_repository),
    inference_repo: InferenceRepository = Depends(get_inference_repository),
):
    """List all elevators with latest health score."""
    elevators = repo.get_all()

    result = []
    for elev in elevators:
        # Get latest inference for health score
        latest = inference_repo.find_latest(elev.id)
        health_score = latest.health_score if latest else None
        status = latest.status if latest else None

        result.append(
            ElevatorResponse(
                id=elev.id,
                max_capacity_kg=elev.max_capacity_kg,
                created_at=elev.created_at,
                latest_health_score=health_score,
                status=status,
            )
        )

    return result


@router.get("/{elevator_id}", response_model=ElevatorResponse)
def get_elevator(
    elevator_id: str,
    repo: ElevatorRepository = Depends(get_elevator_repository),
    inference_repo: InferenceRepository = Depends(get_inference_repository),
):
    """Get a specific elevator by ID."""
    elev = repo.get_by_id(elevator_id)
    if not elev:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Elevator {elevator_id} not found",
        )

    latest = inference_repo.find_latest(elevator_id)
    health_score = latest.health_score if latest else None
    status = latest.status if latest else None

    return ElevatorResponse(
        id=elev.id,
        max_capacity_kg=elev.max_capacity_kg,
        created_at=elev.created_at,
        latest_health_score=health_score,
        status=status,
    )


@router.get("/{elevator_id}/readings", response_model=List[SensorReadingResponse])
def get_readings(
    elevator_id: str,
    from_time: Optional[datetime] = None,
    to_time: Optional[datetime] = None,
    sensor_id: Optional[str] = None,
    limit: int = 500,
    repo: ReadingRepository = Depends(get_reading_repository),
    elev_repo: ElevatorRepository = Depends(get_elevator_repository),
):
    """Get paginated sensor readings for an elevator."""
    # Verify elevator exists
    if not elev_repo.get_by_id(elevator_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Elevator {elevator_id} not found",
        )

    # Cap limit
    limit = min(limit, 5000)

    readings = repo.find_by_elevator(
        elevator_id=elevator_id,
        from_time=from_time,
        to_time=to_time,
        sensor_id=sensor_id,
        limit=limit,
    )

    return [
        SensorReadingResponse(
            id=r.id,
            elevator_id=r.elevator_id,
            timestamp=r.timestamp,
            accel_rms_mg=r.accel_rms_mg,
            velocity_rms_mms=r.velocity_rms_mms,
            peak_accel_mg=r.peak_accel_mg,
            vib_temperature_c=r.vib_temperature_c,
            env_temperature_c=r.env_temperature_c,
            env_humidity_pct=r.env_humidity_pct,
            load_kg=r.load_kg,
            synced=r.synced,
        )
        for r in readings
    ]
