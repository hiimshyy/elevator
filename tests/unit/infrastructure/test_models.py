"""Tests for SQLAlchemy ORM models and database initialization."""
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from elevator_pdm.infrastructure.persistence.models import (
    Base, Elevator, SensorReading, InferenceResult, Alert, MaintenanceSchedule
)
from elevator_pdm.infrastructure.persistence.database import init_db, create_engine_and_session


def test_create_all_creates_five_tables():
    engine, SessionLocal = create_engine_and_session("sqlite:///:memory:")
    init_db(engine)

    inspector = inspect(engine)
    tables = inspector.get_table_names()
    assert "elevators" in tables
    assert "sensor_readings" in tables
    assert "inference_results" in tables
    assert "alerts" in tables
    assert "maintenance_schedule" in tables
    assert len(tables) >= 5


def test_indexes_on_sensor_readings():
    engine, SessionLocal = create_engine_and_session("sqlite:///:memory:")
    init_db(engine)

    inspector = inspect(engine)
    indexes = inspector.get_indexes("sensor_readings")
    index_columns = [tuple(idx["column_names"]) for idx in indexes]
    assert any("elevator_id" in cols and "timestamp" in cols for cols in index_columns)


def test_indexes_on_inference_results():
    engine, SessionLocal = create_engine_and_session("sqlite:///:memory:")
    init_db(engine)

    inspector = inspect(engine)
    indexes = inspector.get_indexes("inference_results")
    index_columns = [tuple(idx["column_names"]) for idx in indexes]
    assert any("elevator_id" in cols and "timestamp" in cols for cols in index_columns)


def test_fk_constraints_enforced():
    engine, SessionLocal = create_engine_and_session("sqlite:///:memory:")
    init_db(engine)
    session = SessionLocal()

    # Try to insert a reading with non-existent elevator_id
    reading = SensorReading(elevator_id="nonexistent", sensor_id="ES-VS-01", timestamp="2025-01-01T00:00:00+00:00")
    session.add(reading)
    with pytest.raises(IntegrityError):  # Should raise IntegrityError due to FK constraint
        session.commit()
    session.rollback()
    session.close()


def test_insert_and_query_elevator():
    engine, SessionLocal = create_engine_and_session("sqlite:///:memory:")
    init_db(engine)
    session = SessionLocal()

    elevator = Elevator(
        name="Test Elevator",
        location="Building A",
        max_capacity_kg=1000,
        install_date="2025-01-01"
    )
    session.add(elevator)
    session.commit()

    result = session.query(Elevator).filter_by(name="Test Elevator").first()
    assert result is not None
    assert result.name == "Test Elevator"
    assert result.max_capacity_kg == 1000
    session.close()


def test_insert_and_query_sensor_reading():
    engine, SessionLocal = create_engine_and_session("sqlite:///:memory:")
    init_db(engine)
    session = SessionLocal()

    # First create an elevator
    elevator = Elevator(
        name="Test Elevator",
        location="Building A",
        max_capacity_kg=1000,
        install_date="2025-01-01"
    )
    session.add(elevator)
    session.commit()

    reading = SensorReading(
        elevator_id=elevator.id,
        sensor_id="ES-VS-01",
        timestamp="2025-01-01T00:00:00+00:00",
        accel_rms_mg=42.5,
        velocity_rms_mms=12.3,
        peak_accel_mg=98.0,
    )
    session.add(reading)
    session.commit()

    result = session.query(SensorReading).filter_by(elevator_id=elevator.id).first()
    assert result is not None
    assert result.accel_rms_mg == 42.5
    assert result.sensor_id == "ES-VS-01"
    session.close()


def test_insert_and_query_inference_result():
    engine, SessionLocal = create_engine_and_session("sqlite:///:memory:")
    init_db(engine)
    session = SessionLocal()

    elevator = Elevator(
        name="Test Elevator",
        location="Building A",
        max_capacity_kg=1000,
        install_date="2025-01-01"
    )
    session.add(elevator)
    session.commit()

    inference = InferenceResult(
        elevator_id=elevator.id,
        timestamp="2025-01-01T00:00:00+00:00",
        model_name="vibration_anomaly",
        model_version="1.0",
        status="NORMAL",
        confidence=0.95,
        health_score=85.0,
    )
    session.add(inference)
    session.commit()

    result = session.query(InferenceResult).filter_by(elevator_id=elevator.id).first()
    assert result is not None
    assert result.status == "NORMAL"
    assert result.confidence == 0.95
    session.close()


def test_insert_and_query_alert():
    engine, SessionLocal = create_engine_and_session("sqlite:///:memory:")
    init_db(engine)
    session = SessionLocal()

    elevator = Elevator(
        name="Test Elevator",
        location="Building A",
        max_capacity_kg=1000,
        install_date="2025-01-01"
    )
    session.add(elevator)
    session.commit()

    alert = Alert(
        elevator_id=elevator.id,
        alert_type="VIBRATION_HIGH",
        severity="WARNING",
        message="High vibration detected",
        sent_at="2025-01-01T00:00:00+00:00",
        channel="slack",
    )
    session.add(alert)
    session.commit()

    result = session.query(Alert).filter_by(elevator_id=elevator.id).first()
    assert result is not None
    assert result.severity == "WARNING"
    assert result.channel == "slack"
    session.close()


def test_insert_and_query_maintenance():
    engine, SessionLocal = create_engine_and_session("sqlite:///:memory:")
    init_db(engine)
    session = SessionLocal()

    elevator = Elevator(
        name="Test Elevator",
        location="Building A",
        max_capacity_kg=1000,
        install_date="2025-01-01"
    )
    session.add(elevator)
    session.commit()

    maintenance = MaintenanceSchedule(
        elevator_id=elevator.id,
        recommended_date="2025-02-01",
        urgency="routine",
        reason="Regular maintenance",
        created_at="2025-01-01T00:00:00+00:00",
    )
    session.add(maintenance)
    session.commit()

    result = session.query(MaintenanceSchedule).filter_by(elevator_id=elevator.id).first()
    assert result is not None
    assert result.urgency == "routine"
    assert result.status == "pending"
    session.close()
