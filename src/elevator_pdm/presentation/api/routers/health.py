"""Health check & Model reload routers (Task D7)."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from elevator_pdm.presentation.api.dependencies import (
    get_db_session,
    get_sensor_gateway,
    get_vibration_runtime,
    get_health_runtime,
)
from elevator_pdm.infrastructure.sensors.mock_gateway import MockSensorGateway
from elevator_pdm.infrastructure.ml.onnx_runtime import OnnxRuntime
from elevator_pdm.presentation.api.schemas.responses import HealthCheckResponse

router = APIRouter()


@router.get("/", response_model=HealthCheckResponse)
async def health_check(
    session: Session = Depends(get_db_session),
    sensor_gw: MockSensorGateway = Depends(get_sensor_gateway),
    vibration_rt: OnnxRuntime = Depends(get_vibration_runtime),
    health_rt: OnnxRuntime = Depends(get_health_runtime),
):
    """Check DB connectivity, sensor status, model loaded status."""
    # Check DB
    try:
        session.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "degraded"

    # Check sensors (mock gateway always returns ok)
    try:
        sensor_gw.read_vibration()
        sensors_status = "ok"
    except Exception:
        sensors_status = "degraded"

    # Check models
    models_status = "ok"
    if vibration_rt._session is None:
        try:
            vibration_rt._load_model()
        except Exception:
            models_status = "degraded"
    if health_rt._session is None:
        try:
            health_rt._load_model()
        except Exception:
            models_status = "degraded"

    return HealthCheckResponse(
        db=db_status,
        sensors=sensors_status,
        models=models_status,
    )


@router.post("/reload", response_model=dict)
async def reload_models(
    vibration_rt: OnnxRuntime = Depends(get_vibration_runtime),
    health_rt: OnnxRuntime = Depends(get_health_runtime),
):
    """Hot-reload ONNX models from disk."""
    try:
        vibration_rt.reload()
        health_rt.reload()
        return {"status": "ok", "message": "Models reloaded successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Model reload failed: {e}",
        )
