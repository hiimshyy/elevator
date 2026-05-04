"""SQLAlchemy ORM models for all 5 tables."""
from sqlalchemy import (
    Column, String, Float, Integer, Text, Boolean, Index,
    create_engine, ForeignKey, CheckConstraint
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker, Session
from datetime import datetime, timezone
import uuid

Base = declarative_base()


class Elevator(Base):
    __tablename__ = "elevators"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    location = Column(String, nullable=False)
    max_capacity_kg = Column(Float, nullable=False)
    install_date = Column(String, nullable=False)
    last_maintenance = Column(String, nullable=True)
    status = Column(String, default="active")
    created_at = Column(String, default=lambda: datetime.now(timezone.utc).isoformat())

    readings = relationship("SensorReading", back_populates="elevator")
    inference_results = relationship("InferenceResult", back_populates="elevator")
    alerts = relationship("Alert", back_populates="elevator")
    maintenance = relationship("MaintenanceSchedule", back_populates="elevator")

    __table_args__ = (
        CheckConstraint("status IN ('active', 'decommissioned', 'maintenance')", name="check_status"),
    )


class SensorReading(Base):
    __tablename__ = "sensor_readings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    elevator_id = Column(String, ForeignKey("elevators.id"), nullable=False)
    sensor_id = Column(String, nullable=False)
    timestamp = Column(String, nullable=False)
    accel_rms_mg = Column(Float, nullable=True)
    velocity_rms_mms = Column(Float, nullable=True)
    peak_accel_mg = Column(Float, nullable=True)
    vib_temperature_c = Column(Float, nullable=True)
    env_temperature_c = Column(Float, nullable=True)
    env_humidity_pct = Column(Float, nullable=True)
    load_kg = Column(Float, nullable=True)
    synced = Column(Integer, default=0)

    elevator = relationship("Elevator", back_populates="readings")

    __table_args__ = (
        Index("idx_readings_elevator_time", "elevator_id", "timestamp"),
    )


class InferenceResult(Base):
    __tablename__ = "inference_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    elevator_id = Column(String, ForeignKey("elevators.id"), nullable=False)
    timestamp = Column(String, nullable=False)
    model_name = Column(String, nullable=False)
    model_version = Column(String, nullable=False)
    status = Column(String, nullable=False)
    confidence = Column(Float, nullable=True)
    health_score = Column(Float, nullable=True)
    features_json = Column(Text, nullable=True)
    synced = Column(Integer, default=0)

    elevator = relationship("Elevator", back_populates="inference_results")

    __table_args__ = (
        Index("idx_inference_elevator_time", "elevator_id", "timestamp"),
        CheckConstraint("status IN ('NORMAL', 'WARNING', 'CRITICAL', 'OVERLOAD')", name="check_status"),
    )


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    elevator_id = Column(String, ForeignKey("elevators.id"), nullable=False)
    inference_id = Column(Integer, ForeignKey("inference_results.id"), nullable=True)
    alert_type = Column(String, nullable=False)
    severity = Column(String, nullable=False)
    message = Column(String, nullable=False)
    sent_at = Column(String, nullable=False)
    channel = Column(String, nullable=False)
    acknowledged = Column(Integer, default=0)
    acknowledged_by = Column(String, nullable=True)
    acknowledged_at = Column(String, nullable=True)

    elevator = relationship("Elevator", back_populates="alerts")

    __table_args__ = (
        CheckConstraint("severity IN ('WARNING', 'CRITICAL', 'EMERGENCY')", name="check_severity"),
        CheckConstraint("channel IN ('slack', 'email', 'sms')", name="check_channel"),
    )


class MaintenanceSchedule(Base):
    __tablename__ = "maintenance_schedule"

    id = Column(Integer, primary_key=True, autoincrement=True)
    elevator_id = Column(String, ForeignKey("elevators.id"), nullable=False)
    recommended_date = Column(String, nullable=False)
    urgency = Column(String, nullable=False)
    reason = Column(String, nullable=False)
    estimated_rul_hours = Column(Float, nullable=True)
    status = Column(String, default="pending")
    completed_at = Column(String, nullable=True)
    technician = Column(String, nullable=True)
    created_at = Column(String, nullable=False)

    elevator = relationship("Elevator", back_populates="maintenance")

    __table_args__ = (
        CheckConstraint("urgency IN ('routine', 'soon', 'urgent', 'immediate')", name="check_urgency"),
        CheckConstraint("status IN ('pending', 'scheduled', 'completed', 'cancelled')", name="check_status"),
    )
