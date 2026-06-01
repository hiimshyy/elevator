"""Tests for AlertPipelineWorker."""

from elevator_pdm.application.services.alert_pipeline_worker import AlertPipelineWorker


def test_run_once_processes_all_elevators() -> None:
    processed: list[tuple[str, int]] = []

    worker = AlertPipelineWorker(
        list_elevator_ids=lambda: ["elev-001", "elev-002"],
        process_elevator=lambda elevator_id, limit: (
            processed.append((elevator_id, limit))
            or {"elevator_id": elevator_id, "processed_readings": limit}
        ),
    )

    summaries = worker.run_once(limit=42)

    assert processed == [("elev-001", 42), ("elev-002", 42)]
    assert [summary["elevator_id"] for summary in summaries] == ["elev-001", "elev-002"]


def test_run_forever_respects_max_cycles() -> None:
    processed: list[tuple[str, int]] = []
    sleep_calls: list[float] = []

    worker = AlertPipelineWorker(
        list_elevator_ids=lambda: ["elev-001"],
        process_elevator=lambda elevator_id, limit: (
            processed.append((elevator_id, limit))
            or {"elevator_id": elevator_id, "processed_readings": limit}
        ),
        sleep_fn=lambda seconds: sleep_calls.append(seconds),
    )

    worker.run_forever(limit=10, interval_s=7, max_cycles=3)

    assert processed == [("elev-001", 10), ("elev-001", 10), ("elev-001", 10)]
    assert sleep_calls == [7, 7]
