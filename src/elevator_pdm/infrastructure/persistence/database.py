"""SQLAlchemy engine and session factory."""
from collections.abc import Generator

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from elevator_pdm.infrastructure.persistence.models import Base


def create_engine_and_session(db_url: str = "sqlite:///data/elevator.db"):
    """Create engine and session factory for the given database URL."""
    engine = create_engine(db_url, echo=False)

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    session_local = sessionmaker(bind=engine)
    return engine, session_local


def init_db(engine) -> None:
    """Create all tables."""
    Base.metadata.create_all(bind=engine)
    _ensure_sensor_readings_columns(engine)


def _ensure_sensor_readings_columns(engine) -> None:
    inspector = inspect(engine)
    if "sensor_readings" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("sensor_readings")}
    missing_columns = {
        "controller_register_1047": "INTEGER",
        "controller_register_0x2121": "INTEGER",
        "controller_register_0x2122": "INTEGER",
    }

    with engine.begin() as connection:
        for column_name, column_type in missing_columns.items():
            if column_name in existing_columns:
                continue
            connection.execute(
                text(
                    f"ALTER TABLE sensor_readings ADD COLUMN {column_name} {column_type}"
                )
            )


def get_db(session_factory) -> Generator[Session, None, None]:
    """FastAPI dependency for database sessions."""
    db = session_factory()
    try:
        yield db
    finally:
        db.close()
