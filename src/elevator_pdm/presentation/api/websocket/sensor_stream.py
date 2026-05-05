"""WebSocket sensor stream (Task D8)."""
import json
import asyncio
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status

from elevator_pdm.presentation.api.dependencies import get_reading_repository
from elevator_pdm.presentation.api.dependencies import get_inference_repository
from elevator_pdm.domain.interfaces.reading_repository import ReadingRepository
from elevator_pdm.domain.interfaces.inference_repository import InferenceRepository

router = APIRouter()


@router.websocket("/ws/sensors/{elevator_id}")
async def sensor_stream(
    websocket: WebSocket,
    elevator_id: str,
    reading_repo: ReadingRepository = Depends(get_reading_repository),
    inference_repo: InferenceRepository = Depends(get_inference_repository),
):
    """Push JSON every 5s with latest readings + inference result.

    Auto-disconnect on invalid elevator_id.
    """
    # Verify elevator exists (check if any readings exist)
    readings = reading_repo.find_by_elevator(elevator_id, limit=1)
    if not readings:
        await websocket.close(code=4404, reason=f"Elevator {elevator_id} not found")
        return

    await websocket.accept()

    try:
        while True:
            # Get latest reading
            latest_reading = reading_repo.find_latest(elevator_id)
            latest_inference = inference_repo.find_latest(elevator_id)

            # Build message
            message = {
                "event": "sensor_update",
                "elevator_id": elevator_id,
                "timestamp": latest_reading.timestamp.isoformat() if latest_reading else None,
                "readings": {
                    "accel_rms_mg": latest_reading.accel_rms_mg if latest_reading else None,
                    "velocity_rms_mms": latest_reading.velocity_rms_mms if latest_reading else None,
                    "peak_accel_mg": latest_reading.peak_accel_mg if latest_reading else None,
                    "vib_temperature_c": latest_reading.vib_temperature_c if latest_reading else None,
                    "env_temperature_c": latest_reading.env_temperature_c if latest_reading else None,
                    "env_humidity_pct": latest_reading.env_humidity_pct if latest_reading else None,
                    "load_kg": latest_reading.load_kg if latest_reading else None,
                } if latest_reading else None,
                "inference": {
                    "status": latest_inference.status if latest_inference else None,
                    "confidence": latest_inference.confidence if latest_inference else None,
                    "health_score": latest_inference.health_score if latest_inference else None,
                } if latest_inference else None,
                "alert": latest_inference and latest_inference.status in ("WARNING", "CRITICAL", "OVERLOAD"),
            }

            await websocket.send_json(message)
            await asyncio.sleep(5)  # Push every 5 seconds

    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.close(code=1011, reason=f"Error: {e}")
