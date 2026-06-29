"""Controller telemetry snapshots router (R11.1, R11.2, R11.3)."""
from datetime import datetime

from fastapi import APIRouter, Depends

from elevator_pdm.domain.interfaces.controller_snapshot_repository import (
    ControllerSnapshotRepository,
)
from elevator_pdm.presentation.api.dependencies import get_controller_snapshot_repository
from elevator_pdm.presentation.api.schemas.responses import ControllerSnapshotResponse

router = APIRouter()


@router.get("/{elevator_id}/controller-snapshots", response_model=list[ControllerSnapshotResponse])
def get_controller_snapshots(
    elevator_id: str,
    from_time: datetime | None = None,
    to_time: datetime | None = None,
    limit: int = 500,
    repo: ControllerSnapshotRepository = Depends(get_controller_snapshot_repository),
) -> list[ControllerSnapshotResponse]:
    """Return persisted controller snapshots for an elevator, newest first.

    - R11.1: Results are ordered newest → oldest.
    - R11.2: Supports optional ``from_time`` / ``to_time`` time-range filtering.
    - R11.3: Data is sourced from ``ControllerSnapshotRepository`` (not MQTT).

    Args:
        elevator_id: Elevator identifier.
        from_time: Optional inclusive lower bound for the snapshot timestamp.
        to_time: Optional inclusive upper bound for the snapshot timestamp.
        limit: Maximum number of results to return (capped at 500).
        repo: Injected ``ControllerSnapshotRepository`` implementation.

    Returns:
        List of :class:`ControllerSnapshotResponse` objects, newest first.
    """
    effective_limit = min(limit, 500)
    from_ts = from_time.isoformat() if from_time else None
    to_ts = to_time.isoformat() if to_time else None

    snapshots = repo.find_by_elevator(
        elevator_id=elevator_id,
        from_ts=from_ts,
        to_ts=to_ts,
        limit=effective_limit,
    )

    return [ControllerSnapshotResponse.from_domain(s) for s in snapshots]
