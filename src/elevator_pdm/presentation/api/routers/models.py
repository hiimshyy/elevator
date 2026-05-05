"""Models router (Task D7)."""
from fastapi import APIRouter, Depends, HTTPException, status

from elevator_pdm.presentation.api.dependencies import get_vibration_runtime, get_health_runtime
from elevator_pdm.infrastructure.ml.onnx_runtime import OnnxRuntime
from elevator_pdm.presentation.api.schemas.responses import ModelReloadResponse

router = APIRouter()


@router.post("/reload", response_model=ModelReloadResponse)
async def reload_models(
    vibration_rt: OnnxRuntime = Depends(get_vibration_runtime),
    health_rt: OnnxRuntime = Depends(get_health_runtime),
):
    """Hot-reload ONNX models from disk."""
    try:
        vibration_rt.reload()
        health_rt.reload()
        return ModelReloadResponse(
            status="ok",
            model="all",
            version=f"{vibration_rt.model_version},{health_rt.model_version}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Model reload failed: {e}",
        )


@router.get("/status", response_model=dict)
async def model_status(
    vibration_rt: OnnxRuntime = Depends(get_vibration_runtime),
    health_rt: OnnxRuntime = Depends(get_health_runtime),
):
    """Get model status and versions."""
    return {
        "vibration_anomaly": {
            "loaded": vibration_rt._session is not None,
            "version": vibration_rt.model_version,
        },
        "health_score": {
            "loaded": health_rt._session is not None,
            "version": health_rt.model_version,
        },
    }
