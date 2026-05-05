"""Process Reading Use Case — dequeue → feature engineering → feature vector."""
from typing import Optional, Dict, Any
from dataclasses import asdict

from elevator_pdm.infrastructure.messaging.redis_queue import RedisQueue
from elevator_pdm.application.services.feature_engineer import FeatureEngineer


class ProcessReadingUseCase:
    """Orchestrates: dequeue from Redis → compute features.

    Returns feature dict ready for model input.
    """

    def __init__(
        self,
        redis_queue: RedisQueue,
        feature_engineer: FeatureEngineer,
    ) -> None:
        self._redis_queue = redis_queue
        self._feature_engineer = feature_engineer

    def execute(self, timeout: int = 5) -> Optional[Dict[str, Any]]:
        """Dequeue a reading and compute features.

        Args:
            timeout: Seconds to block waiting for a reading.

        Returns:
            Feature dict ready for model input, or None if queue empty/timeout.
        """
        # Dequeue from Redis
        reading_dict = self._redis_queue.dequeue(timeout=timeout)

        if reading_dict is None:
            return None

        # Compute features
        features = self._feature_engineer.compute(reading_dict)

        return features

    def execute_batch(
        self,
        max_readings: int = 10,
        timeout: int = 1,
    ) -> list[Dict[str, Any]]:
        """Process multiple readings from the queue.

        Args:
            max_readings: Maximum number of readings to process.
            timeout: Timeout per reading.

        Returns:
            List of feature dicts.
        """
        results = []
        for _ in range(max_readings):
            features = self.execute(timeout=timeout)
            if features is None:
                break
            results.append(features)
        return results

    def get_last_features(self) -> Optional[Dict[str, Any]]:
        """Get the last computed feature vector."""
        return self._feature_engineer.get_last_features()
