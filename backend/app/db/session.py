import os
from pathlib import Path
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.core.config import settings
from app.core.logging import db_logger

# Ensure database directory exists if using SQLite
if settings.DATABASE_URL.startswith("sqlite"):
    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
    connect_args = {"check_same_thread": False, "timeout": 30.0}
else:
    connect_args = {}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=False,
    future=True
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    future=True
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Initialize database tables and log status."""
    try:
        from app.db.base import Base
        import app.models.schema  # noqa: F401
        Base.metadata.create_all(bind=engine)
        db_logger.info("Database initialized successfully.")
    except Exception as exc:
        db_logger.error(f"Database initialization failed: {exc}")
        raise
