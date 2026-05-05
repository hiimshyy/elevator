"""Run Inference Use Case — orchestrates feature vector → model → result → event."""
from typing import Dict, Any, Optional

from elevator_pdm.domain.interfaces.model_runtime import ModelRuntime
from elevator_pdm.domain.interfaces.inference_repository import InferenceRepository
from elevator_pdm.domain.interfaces.event_bus import EventBus
from elevator_pdm.domain.entities.inference_result import InferenceResult
from elevator_pdm.domain.exceptions import ModelNotLoadedError


class RunInferenceUseCase:
    """Orchestrates: feature vector → model runtime → save → publish event.

    Publishes 'anomaly_detected' event only for WARNING/CRITICAL status.
    """

    def __init__(
        self,
        model_runtime: ModelRuntime,
        inference_repo: InferenceRepository,
        event_bus: Optional[EventBus] = None,
    ) -> None:
        self._runtime = model_runtime
        self._inference_repo = inference_repo
        self._event_bus = event_bus

    def execute(
        self,
        elevator_id: str,
        features: Dict[str, float],
        model_name: str = "vibration_anomaly",
    ) -> InferenceResult:
        """Run inference on a feature vector.

        Args:
            elevator_id: Which elevator this inference is for.
            features: Feature dict from FeatureEngineer.
            model_name: Name of the model being used.

        Returns:
            InferenceResult with status, confidence, health_score.
        """
        # Run model inference
        try:
            result = self._runtime.predict(features)
        except ModelNotLoadedError as e:
            raise ModelNotLoadedError(f"Inference failed: {e}") from e

        # Set elevator_id and other metadata
        result.elevator_id = elevator_id
        # We can't modify a frozen dataclass, so create a new one
        from dataclasses import replace
        result = replace(
            result,
            elevator_id=elevator_id,
            timestamp=result.timestamp or "",  # Will be set by caller if needed
            model_name=model_name,
            model_version=self._runtime.model_version,
            features_json=str(features),
        )

        # Persist to inference repository
        self._inference_repo.save(result)

        # Publish domain event only for non-NORMAL status
        if result.status != "NORMAL" and self._event_bus:
            event_payload = {
                "elevator_id": elevator_id,
                "status": result.status,
                "confidence": result.confidence,
                "health_score": result.health_score,
                "model_name": model_name,
            }
            self._event_bus.publish("anomaly_detected", event_payload)

        return result
