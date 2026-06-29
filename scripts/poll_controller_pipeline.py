"""Poll the elevator controller, persist snapshots, and publish to MQTT.

This script constructs the controller poll pipeline from ``Settings`` and drives
``PollControllerUseCase.run_forever``.  It is fully separate from
``poll_sensor_pipeline.py`` — no shared state, no cross-calling — so a
controller failure can never interrupt the field-sensor cycle (Requirements
6.3, 6.4, 6.5).
"""
from __future__ import annotations

import logging
import signal
import sys
import types
from typing import Any

from elevator_pdm.application.use_cases.poll_controller import PollControllerUseCase, ReadingQueue
from elevator_pdm.domain.entities.elevator import Elevator
from elevator_pdm.infrastructure.config.settings import Settings
from elevator_pdm.infrastructure.messaging.mqtt_publisher import MqttPublisher
from elevator_pdm.infrastructure.persistence.database import create_engine_and_session, init_db
from elevator_pdm.infrastructure.persistence.sqlite_controller_snapshot_repo import (
    SQLiteControllerSnapshotRepo,
)
from elevator_pdm.infrastructure.persistence.sqlite_elevator_repo import SQLiteElevatorRepo
from elevator_pdm.infrastructure.sensors.pymodbus_controller_gateway import (
    PymodbusControllerGateway,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# No-op queue — mirrors poll_sensor_pipeline._NoopQueue for environments where
# Redis is not available.  Replace with a real RedisQueue adapter when needed.
# ---------------------------------------------------------------------------


class _NoopQueue:
    """Discards every enqueue call; satisfies the ReadingQueue protocol."""

    def enqueue(self, reading: dict[str, object]) -> None:  # noqa: D401
        return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def ensure_database_schema(engine: Any) -> None:
    """Create all tables (including controller_snapshots) if they do not exist."""
    init_db(engine)


def ensure_elevator(session_factory: Any, settings: Settings) -> None:
    """Create the elevator row if it is not yet persisted."""
    session = session_factory()
    try:
        repo = SQLiteElevatorRepo(session)
        if repo.get_by_id(settings.elevator.id):
            return
        repo.create(
            Elevator(
                id=settings.elevator.id,
                name=settings.elevator.id,
                location="Runtime controller pipeline",
                max_capacity_kg=settings.elevator.max_capacity_kg,
                install_date="2024-01-01",
            )
        )
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Signal handling
# ---------------------------------------------------------------------------

_shutdown_requested = False


def _handle_signal(signum: int, frame: types.FrameType | None) -> None:
    global _shutdown_requested
    _shutdown_requested = True
    logger.info("Shutdown signal received (signal %s); stopping controller pipeline.", signum)
    sys.exit(0)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    # Graceful shutdown on SIGINT / SIGTERM
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    settings = Settings()

    # Elevator id and poll interval from Settings — no hardcoded values (R8.6, 9.1)
    elevator_id: str = settings.elevator.id

    # Initialise database and ensure elevator row exists.
    engine, session_factory = create_engine_and_session(settings.database.url)
    ensure_database_schema(engine)
    ensure_elevator(session_factory, settings)

    # Build the MQTT publisher once; reuse across cycles.
    mqtt_publisher = MqttPublisher(settings=settings)
    mqtt_publisher.connect()

    try:
        logger.info(
            "Starting controller poll pipeline for elevator=%s interval=%ss",
            elevator_id,
            settings.controller_telemetry.poll_interval_s,
        )

        # Each cycle opens a fresh SQLAlchemy session so no partial transaction
        # can bleed across cycles.  The gateway and MQTT publisher are stateful
        # but safe to reuse.
        controller_gateway = PymodbusControllerGateway(settings=settings)
        reading_queue: ReadingQueue = _NoopQueue()

        session = session_factory()
        try:
            snapshot_repo = SQLiteControllerSnapshotRepo(session)

            use_case = PollControllerUseCase(
                controller_gateway=controller_gateway,
                snapshot_repo=snapshot_repo,
                reading_queue=reading_queue,
                mqtt_publisher=mqtt_publisher,
                settings=settings,
            )

            # run_forever drives the loop; any controller exception is guarded
            # inside run_forever so it never propagates (R6.4, R6.5, R9.1, R9.3).
            use_case.run_forever(elevator_id=elevator_id)

        finally:
            session.close()

    except KeyboardInterrupt:
        logger.info("Controller pipeline interrupted by keyboard; exiting cleanly.")
    finally:
        mqtt_publisher.disconnect()
        logger.info("Controller poll pipeline stopped.")


if __name__ == "__main__":
    main()
