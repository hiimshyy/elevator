"""FastAPI dependency injection wiring.

Wires concrete implementations to abstract interfaces using Depends().
"""
from typing import Generator

from fastapi import Depends, FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from elevator_pdm.infrastructure.config.settings import Settings
from elevator_pdm.infrastructure.persistence.database import create_engine_and_session
from elevator_pdm.infrastructure.persistence.sqlite_elevator_repo import SQLiteElevatorRepo
from elevator_pdm.infrastructure.persistence.sqlite_reading_repo import SQLiteReadingRepo
from elevator_pdm.infrastructure.persistence.sqlite_inference_repo import SQLiteInferenceRepo
from elevator_pdm.infrastructure.persistence.sqlite_alert_repo import SQLiteAlertRepo
from elevator_pdm.infrastructure.persistence.sqlite_maintenance_repo import SQLiteMaintenanceRepo
from elevator_pdm.infrastructure.ml.onnx_runtime import OnnxRuntime
from elevator_pdm.infrastructure.sensors.mock_gateway import MockGateway


# Module-level singletons (lazy-initialized)
_settings: Settings = None
_engine = None
_session_factory: sessionmaker = None
_sensor_gateway: MockGateway = None
_vibration_runtime: OnnxRuntime = None
_health_runtime: OnnxRuntime = None


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
        db_path = "sqlite:///data/elevator.db"  # TODO: make configurable
        _engine, _ = create_engine_and_session(db_path)
    return _engine


def get_db_session_factory():
    """Get or create session factory singleton."""
    global _session_factory
    if _session_factory is None:
        engine = get_db_engine()
        _session_factory = sessionmaker(bind=engine)
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
) -> SQLiteElevatorRepo:
    """Wire ElevatorRepository implementation."""
    return SQLiteElevatorRepo(session)


def get_reading_repository(
    session: Session = Depends(get_db_session),
) -> SQLiteReadingRepo:
    """Wire ReadingRepository implementation."""
    return SQLiteReadingRepo(session)


def get_inference_repository(
    session: Session = Depends(get_db_session),
) -> SQLiteInferenceRepo:
    """Wire InferenceRepository implementation."""
    return SQLiteInferenceRepo(session)


def get_alert_repository(
    session: Session = Depends(get_db_session),
) -> SQLiteAlertRepo:
    """Wire AlertRepository implementation."""
    return SQLiteAlertRepo(session)


def get_maintenance_repository(
    session: Session = Depends(get_db_session),
) -> SQLiteMaintenanceRepo:
    """Wire MaintenanceRepository implementation."""
    return SQLiteMaintenanceRepo(session)


def get_sensor_gateway() -> MockGateway:
    """Get or create SensorGateway singleton."""
    global _sensor_gateway
    if _sensor_gateway is None:
        _sensor_gateway = MockGateway()
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
