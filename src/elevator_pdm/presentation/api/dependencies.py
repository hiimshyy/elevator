"""FastAPI dependency injection wiring.

Wires concrete implementations to abstract interfaces using Depends().
"""
from typing import Generator

from fastapi import Depends, FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from elevator_pdm.infrastructure.config.settings import Settings
from elevator_pdm.infrastructure.persistence.database import get_engine, get_session_factory
from elevator_pdm.infrastructure.persistence.sqlite_elevator_repo import SqliteElevatorRepository
from elevator_pdm.infrastructure.persistence.sqlite_reading_repo import SqliteReadingRepository
from elevator_pdm.infrastructure.persistence.sqlite_inference_repo import SqliteInferenceRepository
from elevator_pdm.infrastructure.persistence.sqlite_alert_repo import SqliteAlertRepository
from elevator_pdm.infrastructure.persistence.sqlite_maintenance_repo import SqliteMaintenanceRepository
from elevator_pdm.infrastructure.ml.onnx_runtime import OnnxRuntime
from elevator_pdm.infrastructure.sensors.mock_gateway import MockSensorGateway


# Module-level singletons (lazy-initialized)
_settings: Optional[Settings] = None
_engine: Optional[object] = None
_session_factory: Optional[sessionmaker] = None
_sensor_gateway: Optional[MockSensorGateway] = None
_vibration_runtime: Optional[OnnxRuntime] = None
_health_runtime: Optional[OnnxRuntime] = None


def get_settings() -> Settings:
    """Get or create Settings singleton."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def get_db_engine():
    """Get or create database engine singleton."""
    global _engine
    if _engine is None:
        settings = get_settings()
        db_path = "sqlite:///elevator.db"  # TODO: make configurable
        _engine = get_engine(db_path)
    return _engine


def get_db_session_factory():
    """Get or create session factory singleton."""
    global _session_factory
    if _session_factory is None:
        engine = get_db_engine()
        _session_factory = get_session_factory(engine)
    return _session_factory


def get_db_session() -> Generator[Session, None, None]:
    """Create a new database session for each request."""
    factory = get_db_session_factory()
    session = factory()
    try:
        yield session
    finally:
        session.close()


def get_elevator_repository(
    session: Session = Depends(get_db_session),
) -> SqliteElevatorRepository:
    """Wire ElevatorRepository implementation."""
    return SqliteElevatorRepository(session)


def get_reading_repository(
    session: Session = Depends(get_db_session),
) -> SqliteReadingRepository:
    """Wire ReadingRepository implementation."""
    return SqliteReadingRepository(session)


def get_inference_repository(
    session: Session = Depends(get_db_session),
) -> SqliteInferenceRepository:
    """Wire InferenceRepository implementation."""
    return SqliteInferenceRepository(session)


def get_alert_repository(
    session: Session = Depends(get_db_session),
) -> SqliteAlertRepository:
    """Wire AlertRepository implementation."""
    return SqliteAlertRepository(session)


def get_maintenance_repository(
    session: Session = Depends(get_db_session),
) -> SqliteMaintenanceRepository:
    """Wire MaintenanceRepository implementation."""
    return SqliteMaintenanceRepository(session)


def get_sensor_gateway() -> MockSensorGateway:
    """Get or create SensorGateway singleton."""
    global _sensor_gateway
    if _sensor_gateway is None:
        settings = get_settings()
        _sensor_gateway = MockSensorGateway(settings)
    return _sensor_gateway


def get_vibration_runtime() -> OnnxRuntime:
    """Get or create Vibration Anomaly model runtime."""
    global _vibration_runtime
    if _vibration_runtime is None:
        settings = get_settings()
        _vibration_runtime = OnnxRuntime(settings.models.vibration_anomaly)
    return _vibration_runtime


def get_health_runtime() -> OnnxRuntime:
    """Get or create Health Score model runtime."""
    global _health_runtime
    if _health_runtime is None:
        settings = get_settings()
        _health_runtime = OnnxRuntime(settings.models.health_score)
    return _health_runtime
