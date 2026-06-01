"""SQLite implementation of ReadingRepository."""

from sqlalchemy.orm import Session

from elevator_pdm.domain.entities.sensor_reading import SensorReading
from elevator_pdm.domain.interfaces.reading_repository import ReadingRepository
from elevator_pdm.infrastructure.persistence.models import SensorReading as ORMSensorReading


class SQLiteReadingRepo(ReadingRepository):
    """SQLite adapter for ReadingRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def _to_orm(self, reading: SensorReading) -> ORMSensorReading:
        """Convert domain entity to ORM model."""
        return ORMSensorReading(
            elevator_id=reading.elevator_id,
            sensor_id=reading.sensor_id,
            timestamp=reading.timestamp,
            accel_rms_mg=reading.accel_rms_mg,
            velocity_rms_mms=reading.velocity_rms_mms,
            peak_accel_mg=reading.peak_accel_mg,
            vib_temperature_c=reading.vib_temperature_c,
            env_temperature_c=reading.env_temperature_c,
            env_humidity_pct=reading.env_humidity_pct,
            load_kg=reading.load_kg,
        )

    def _to_domain(self, orm_reading: ORMSensorReading) -> SensorReading:
        """Convert ORM model to domain entity."""
        return SensorReading(
            id=orm_reading.id,
            elevator_id=orm_reading.elevator_id,
            sensor_id=orm_reading.sensor_id,
            timestamp=orm_reading.timestamp,
            accel_rms_mg=orm_reading.accel_rms_mg,
            velocity_rms_mms=orm_reading.velocity_rms_mms,
            peak_accel_mg=orm_reading.peak_accel_mg,
            vib_temperature_c=orm_reading.vib_temperature_c,
            env_temperature_c=orm_reading.env_temperature_c,
            env_humidity_pct=orm_reading.env_humidity_pct,
            load_kg=orm_reading.load_kg,
            synced=orm_reading.synced,
        )

    def save(self, reading: SensorReading) -> None:
        """Persist a single sensor reading."""
        orm_reading = self._to_orm(reading)
        self._session.add(orm_reading)
        self._session.commit()

    def find_by_elevator(
        self,
        elevator_id: str,
        from_ts: str | None = None,
        to_ts: str | None = None,
        sensor_id: str | None = None,
        limit: int = 500,
    ) -> list[SensorReading]:
        """Query readings for an elevator with optional filters."""
        query = self._session.query(ORMSensorReading).filter_by(elevator_id=elevator_id)

        if from_ts:
            query = query.filter(ORMSensorReading.timestamp >= from_ts)
        if to_ts:
            query = query.filter(ORMSensorReading.timestamp <= to_ts)
        if sensor_id:
            query = query.filter_by(sensor_id=sensor_id)

        query = query.order_by(ORMSensorReading.timestamp.desc()).limit(limit)
        return [self._to_domain(r) for r in query.all()]

    def find_latest(self, elevator_id: str) -> SensorReading | None:
        """Get the most recent reading for an elevator."""
        orm_reading = (
            self._session.query(ORMSensorReading)
            .filter_by(elevator_id=elevator_id)
            .order_by(ORMSensorReading.timestamp.desc())
            .first()
        )
        return self._to_domain(orm_reading) if orm_reading else None

    def find_unsynced(self, limit: int = 1000) -> list[SensorReading]:
        """Get readings not yet synced to cloud."""
        query = (
            self._session.query(ORMSensorReading)
            .filter_by(synced=0)
            .limit(limit)
        )
        return [self._to_domain(r) for r in query.all()]

    def mark_synced(self, reading_ids: list[int]) -> None:
        """Mark readings as synced to cloud."""
        if not reading_ids:
            return
        self._session.query(ORMSensorReading).filter(
            ORMSensorReading.id.in_(reading_ids)
        ).update({ORMSensorReading.synced: 1}, synchronize_session=False)
        self._session.commit()
