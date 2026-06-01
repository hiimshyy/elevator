"""Worker loop for continuously processing elevator readings into alerts."""
from __future__ import annotations

import time
from collections.abc import Callable


class AlertPipelineWorker:
    """Run the alert-processing pipeline once or on a fixed interval."""

    def __init__(
        self,
        list_elevator_ids: Callable[[], list[str]],
        process_elevator: Callable[[str, int], dict[str, int | str | None]],
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        self._list_elevator_ids = list_elevator_ids
        self._process_elevator = process_elevator
        self._sleep = sleep_fn

    def run_once(
        self,
        *,
        elevator_id: str | None = None,
        limit: int = 500,
    ) -> list[dict[str, int | str | None]]:
        """Process one cycle across one elevator or the full fleet."""
        elevator_ids = [elevator_id] if elevator_id else self._list_elevator_ids()
        return [self._process_elevator(current_id, limit) for current_id in elevator_ids]

    def run_forever(
        self,
        *,
        elevator_id: str | None = None,
        limit: int = 500,
        interval_s: int = 30,
        max_cycles: int | None = None,
    ) -> None:
        """Run the worker loop until interrupted or until max_cycles is reached."""
        cycle = 0
        while True:
            self.run_once(elevator_id=elevator_id, limit=limit)
            cycle += 1

            if max_cycles is not None and cycle >= max_cycles:
                return

            self._sleep(interval_s)
