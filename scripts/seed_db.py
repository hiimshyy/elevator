"""Seed the local SQLite database with demo elevator readings."""

from __future__ import annotations

import argparse
import math
import random
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def parse_args() -> argparse.Namespace:
    from elevator_pdm.infrastructure.config.settings import Settings

    settings = Settings()
    parser = argparse.ArgumentParser(description="Seed demo elevator data into SQLite.")
    parser.add_argument("--db-url", default=settings.database.url)
    parser.add_argument("--elevator-id", default="elev-001")
    parser.add_argument("--samples", type=int, default=60)
    parser.add_argument("--interval-seconds", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--replace", action="store_true")
    return parser.parse_args()


def ensure_elevator(session, elevator_id: str) -> None:
    from elevator_pdm.infrastructure.persistence.models import Elevator

    existing = session.query(Elevator).filter_by(id=elevator_id).first()
    if existing:
        return

    session.add(
        Elevator(
            id=elevator_id,
            name=f"Elevator {elevator_id}",
            location="Demo Site",
            max_capacity_kg=1600.0,
            install_date="2024-01-01",
            status="active",
        )
    )
    session.commit()


def build_reading(
    elevator_id: str,
    timestamp: datetime,
    rng: random.Random,
    index: int,
):
    from elevator_pdm.infrastructure.persistence.models import SensorReading

    phase = index / 6.0
    accel_rms = 110.0 + math.sin(phase) * 18.0 + rng.uniform(-4.0, 4.0)
    velocity_rms = 4.2 + math.cos(phase / 2.0) * 0.8 + rng.uniform(-0.2, 0.2)
    peak_accel = accel_rms * 1.9 + rng.uniform(5.0, 15.0)
    vib_temp = 41.0 + math.sin(phase / 3.0) * 2.2 + rng.uniform(-0.4, 0.4)
    env_temp = 29.0 + math.cos(phase / 4.0) * 1.4 + rng.uniform(-0.3, 0.3)
    humidity = 58.0 + math.sin(phase / 5.0) * 4.0 + rng.uniform(-0.8, 0.8)
    load = 480.0 + math.sin(phase / 2.5) * 140.0 + rng.uniform(-25.0, 25.0)

    return SensorReading(
        elevator_id=elevator_id,
        sensor_id="LIVE-DEMO",
        timestamp=timestamp.isoformat(),
        accel_rms_mg=round(accel_rms, 2),
        velocity_rms_mms=round(max(velocity_rms, 0.1), 2),
        peak_accel_mg=round(max(peak_accel, 1.0), 2),
        vib_temperature_c=round(vib_temp, 2),
        env_temperature_c=round(env_temp, 2),
        env_humidity_pct=round(min(max(humidity, 0.0), 100.0), 2),
        load_kg=round(max(load, 0.0), 2),
    )


def main() -> int:
    from elevator_pdm.infrastructure.persistence.database import create_engine_and_session, init_db
    from elevator_pdm.infrastructure.persistence.models import SensorReading

    args = parse_args()

    engine, session_factory = create_engine_and_session(args.db_url)
    init_db(engine)
    session = session_factory()

    try:
        ensure_elevator(session, args.elevator_id)

        if args.replace:
            session.query(SensorReading).filter_by(elevator_id=args.elevator_id).delete()
            session.commit()

        rng = random.Random(args.seed)
        start_time = datetime.now(UTC) - timedelta(
            seconds=(args.samples - 1) * args.interval_seconds
        )

        created = 0
        for index in range(args.samples):
            reading = build_reading(
                args.elevator_id,
                start_time + timedelta(seconds=index * args.interval_seconds),
                rng,
                index,
            )
            session.add(reading)
            created += 1

        session.commit()
        total = session.query(SensorReading).filter_by(elevator_id=args.elevator_id).count()
    finally:
        session.close()

    print(
        f"Seeded {created} readings for {args.elevator_id}. "
        f"Total readings for elevator: {total}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
