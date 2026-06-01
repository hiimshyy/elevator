"""Run inference use case."""
import json
from datetime import UTC, datetime

from elevator_pdm.domain.entities.inference_result import InferenceResult
from elevator_pdm.domain.exceptions import ModelNotLoadedError
from elevator_pdm.domain.interfaces.event_bus import EventBus
from elevator_pdm.domain.interfaces.inference_repository import InferenceRepository
from elevator_pdm.domain.interfaces.model_runtime import ModelRuntime


class RunInferenceUseCase:
    """Run a model, persist the result, and publish anomaly events."""

    def __init__(
        self,
        model_runtime: ModelRuntime,
        inference_repo: InferenceRepository,
        event_bus: EventBus | None = None,
    ) -> None:
        self._runtime = model_runtime
        self._inference_repo = inference_repo
        self._event_bus = event_bus

    def execute(
        self,
        elevator_id: str,
        features: dict[str, float],
        model_name: str = "vibration_anomaly",
        timestamp: str | None = None,
    ) -> InferenceResult:
        """Run inference on a feature vector and persist the result."""
        try:
            result = self._runtime.predict(features)
        except ModelNotLoadedError as exc:
            raise ModelNotLoadedError(f"Inference failed: {exc}") from exc

        from dataclasses import replace

        persisted_result = replace(
            result,
            elevator_id=elevator_id,
            timestamp=timestamp or result.timestamp or datetime.now(UTC).isoformat(),
            model_name=model_name,
            model_version=self._runtime.model_version,
            features_json=json.dumps(features, sort_keys=True),
        )

        self._inference_repo.save(persisted_result)

        if persisted_result.status != "NORMAL" and self._event_bus:
            self._event_bus.publish(
                "anomaly_detected",
                {
                    "elevator_id": elevator_id,
                    "status": persisted_result.status,
                    "confidence": persisted_result.confidence,
                    "health_score": persisted_result.health_score,
                    "model_name": model_name,
                },
            )

        return persisted_result
