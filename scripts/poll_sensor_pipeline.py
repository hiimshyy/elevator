"""Poll sensors, persist readings, and publish them to MQTT."""
from __future__ import annotations

import argparse
import time

from elevator_pdm.application.use_cases.poll_sensors import PollSensorsUseCase
from elevator_pdm.domain.entities.elevator import Elevator
from elevator_pdm.domain.interfaces.sensor_gateway import SensorGateway
from elevator_pdm.infrastructure.config.settings import Settings
from elevator_pdm.infrastructure.messaging.mqtt_publisher import MqttPublisher
from elevator_pdm.infrastructure.persistence.database import create_engine_and_session, init_db
from elevator_pdm.infrastructure.persistence.sqlite_elevator_repo import SQLiteElevatorRepo
from elevator_pdm.infrastructure.persistence.sqlite_reading_repo import SQLiteReadingRepo
from elevator_pdm.infrastructure.sensors.mock_gateway import MockGateway
from elevator_pdm.infrastructure.sensors.modbus_gateway import ModbusGateway


class _NoopQueue:
    def enqueue(self, reading: dict) -> None:
        return None


def ensure_database_schema(engine) -> None:
    init_db(engine)


def build_sensor_gateway(settings: Settings, gateway_name: str | None) -> SensorGateway:
    selected_gateway = gateway_name or settings.sensors.source
    if selected_gateway == "modbus":
        return ModbusGateway(settings=settings)
    return MockGateway()


def ensure_elevator(session_factory, settings: Settings) -> None:
    session = session_factory()
    try:
        repo = SQLiteElevatorRepo(session)
        if repo.get_by_id(settings.elevator.id):
            return

        repo.create(
            Elevator(
                id=settings.elevator.id,
                name=settings.elevator.id,
                location="Runtime sensor pipeline",
                max_capacity_kg=settings.elevator.max_capacity_kg,
                install_date="2024-01-01",
            )
        )
    finally:
        session.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elevator-id", help="Override elevator id from settings")
    parser.add_argument("--interval-s", type=int, help="Polling interval in seconds")
    parser.add_argument("--max-cycles", type=int, help="Stop after N cycles")
    parser.add_argument(
        "--gateway",
        choices=("mock", "modbus"),
        help="Select mock data or real RS-485 Modbus polling",
    )
    args = parser.parse_args()

    settings = Settings()
    elevator_id = args.elevator_id or settings.elevator.id
    interval_s = args.interval_s or settings.sensors.vibration.poll_interval_s
    engine, session_factory = create_engine_and_session(settings.database.url)
    ensure_database_schema(engine)
    ensure_elevator(session_factory, settings)
    sensor_gateway = build_sensor_gateway(settings, args.gateway)

    mqtt_publisher = MqttPublisher(settings=settings)
    mqtt_publisher.connect()

    try:
        cycle = 0
        while True:
            session = session_factory()
            try:
                use_case = PollSensorsUseCase(
                    sensor_gateway=sensor_gateway,
                    reading_repo=SQLiteReadingRepo(session),
                    redis_queue=_NoopQueue(),
                    mqtt_publisher=mqtt_publisher,
                )
                use_case.execute(elevator_id=elevator_id)
            finally:
                session.close()

            cycle += 1
            if args.max_cycles is not None and cycle >= args.max_cycles:
                return

            time.sleep(interval_s)
    finally:
        mqtt_publisher.disconnect()


if __name__ == "__main__":
    main()
