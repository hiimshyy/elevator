"""SQLAlchemy engine and session factory."""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator

from elevator_pdm.infrastructure.persistence.models import Base


def create_engine_and_session(db_url: str = "sqlite:///data/elevator.db"):
    """Create engine and session factory for the given database URL."""
    engine = create_engine(db_url, echo=False)

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    SessionLocal = sessionmaker(bind=engine)
    return engine, SessionLocal


def init_db(engine) -> None:
    """Create all tables."""
    Base.metadata.create_all(bind=engine)


def get_db(session_factory) -> Generator[Session, None, None]:
    """FastAPI dependency for database sessions."""
    db = session_factory()
    try:
        yield db
    finally:
        db.close()
