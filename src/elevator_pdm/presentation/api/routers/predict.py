"""Predict router (Task D4)."""
import time

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from elevator_pdm.application.services.feature_engineer import FeatureEngineer
from elevator_pdm.application.use_cases.run_inference import RunInferenceUseCase as RunInference
from elevator_pdm.domain.interfaces.inference_repository import InferenceRepository
from elevator_pdm.domain.interfaces.reading_repository import ReadingRepository
from elevator_pdm.infrastructure.ml.onnx_runtime import OnnxRuntime
from elevator_pdm.infrastructure.sensors.mock_gateway import MockGateway
from elevator_pdm.presentation.api.dependencies import (
    get_db_session,
    get_health_runtime,
    get_inference_repository,
    get_reading_repository,
    get_sensor_gateway,
    get_vibration_runtime,
)
from elevator_pdm.presentation.api.schemas.requests import PredictRequest
from elevator_pdm.presentation.api.schemas.responses import PredictResponse

router = APIRouter()


@router.post("/predict", response_model=PredictResponse)
async def predict(
    request: PredictRequest,
    session: Session = Depends(get_db_session),
    reading_repo: ReadingRepository = Depends(get_reading_repository),
    inference_repo: InferenceRepository = Depends(get_inference_repository),
    vibration_runtime: OnnxRuntime = Depends(get_vibration_runtime),
    health_runtime: OnnxRuntime = Depends(get_health_runtime),
    sensor_gw: MockGateway = Depends(get_sensor_gateway),
):
    """Run inference on sensor readings.

    Accepts sensor readings JSON, runs feature engineering + inference,
    returns status/confidence/health_score/features/alert_triggered/model_version/inference_ms.
    """
    # Check if models are loaded
    if not vibration_runtime._session:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Vibration model not loaded",
        )

    # Create feature engineer
    settings = sensor_gw._settings if hasattr(sensor_gw, '_settings') else None
    max_capacity = settings.elevator.max_capacity_kg if settings else 1000
    feature_engineer = FeatureEngineer(max_capacity_kg=max_capacity)

    # Convert request readings to dict
    readings_dict = request.readings.dict()
    readings_dict = {k: v for k, v in readings_dict.items() if v is not None}

    # Compute features
    features = feature_engineer.compute(readings_dict)

    # Run inference use case
    start_time = time.time()

    use_case = RunInference(
        model_runtime=vibration_runtime,
        inference_repo=inference_repo,
        event_bus=None,  # No event bus for predict endpoint
    )

    inference_result = use_case.execute(
        elevator_id=request.elevator_id,
        features=features,
    )

    inference_ms = (time.time() - start_time) * 1000

    # Check if alert triggered
    alert_triggered = inference_result.status in ("WARNING", "CRITICAL", "OVERLOAD")

    return PredictResponse(
        elevator_id=inference_result.elevator_id,
        status=inference_result.status,
        confidence=inference_result.confidence,
        health_score=inference_result.health_score,
        features=features,
        alert_triggered=alert_triggered,
        model_version=inference_result.model_version,
        inference_ms=inference_ms,
    )
