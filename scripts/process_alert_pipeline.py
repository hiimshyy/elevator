"""Process persisted readings into inference results and alerts."""
from __future__ import annotations

import argparse
import json

from elevator_pdm.application.services.alert_pipeline_worker import AlertPipelineWorker
from elevator_pdm.application.use_cases.process_elevator_readings import (
    ProcessElevatorReadingsUseCase,
)
from elevator_pdm.infrastructure.config.settings import Settings
from elevator_pdm.infrastructure.messaging.mqtt_publisher import MqttPublisher
from elevator_pdm.infrastructure.ml.onnx_runtime import OnnxRuntime
from elevator_pdm.infrastructure.persistence.database import create_engine_and_session
from elevator_pdm.infrastructure.persistence.sqlite_alert_repo import SQLiteAlertRepo
from elevator_pdm.infrastructure.persistence.sqlite_elevator_repo import SQLiteElevatorRepo
from elevator_pdm.infrastructure.persistence.sqlite_inference_repo import SQLiteInferenceRepo
from elevator_pdm.infrastructure.persistence.sqlite_reading_repo import SQLiteReadingRepo


def ensure_database_schema(engine) -> None:
    """Create missing tables so worker can start before API."""
    from elevator_pdm.infrastructure.persistence import models

    models.Base.metadata.create_all(bind=engine)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elevator-id", help="Only process one elevator")
    parser.add_argument(
        "--limit",
        type=int,
        help="Max readings to inspect per elevator",
    )
    parser.add_argument(
        "--interval-s",
        type=int,
        help="Worker interval in seconds for looping mode",
    )
    parser.add_argument(
        "--max-cycles",
        type=int,
        help="Optional number of cycles to run before exiting",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run one cycle and print the summaries as JSON",
    )
    args = parser.parse_args()

    settings = Settings()
    limit = args.limit or settings.workers.alert_pipeline_limit
    interval_s = args.interval_s or settings.workers.alert_pipeline_interval_s
    engine, session_factory = create_engine_and_session(settings.database.url)
    ensure_database_schema(engine)
    mqtt_publisher = MqttPublisher(settings=settings)
    mqtt_publisher.connect()

    def list_elevator_ids() -> list[str]:
        session = session_factory()
        try:
            elevator_repo = SQLiteElevatorRepo(session)
            return [elevator.id for elevator in elevator_repo.get_all()]
        finally:
            session.close()

    def process_elevator(elevator_id: str, reading_limit: int) -> dict[str, int | str | None]:
        session = session_factory()
        try:
            elevator_repo = SQLiteElevatorRepo(session)
            reading_repo = SQLiteReadingRepo(session)
            inference_repo = SQLiteInferenceRepo(session)
            alert_repo = SQLiteAlertRepo(session)
            runtime = OnnxRuntime(settings.models.vibration_anomaly)

            use_case = ProcessElevatorReadingsUseCase(
                elevator_repo=elevator_repo,
                reading_repo=reading_repo,
                inference_repo=inference_repo,
                alert_repo=alert_repo,
                model_runtime=runtime,
                settings=settings,
                mqtt_publisher=mqtt_publisher,
            )
            return use_case.execute(elevator_id=elevator_id, limit=reading_limit)
        finally:
            session.close()

    worker = AlertPipelineWorker(
        list_elevator_ids=list_elevator_ids,
        process_elevator=process_elevator,
    )

    try:
        if args.once or args.max_cycles == 1:
            summaries = worker.run_once(elevator_id=args.elevator_id, limit=limit)
            print(json.dumps(summaries, indent=2))
            return

        worker.run_forever(
            elevator_id=args.elevator_id,
            limit=limit,
            interval_s=interval_s,
            max_cycles=args.max_cycles,
        )
    finally:
        mqtt_publisher.disconnect()


if __name__ == "__main__":
    main()
