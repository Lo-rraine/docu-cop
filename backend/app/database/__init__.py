import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.config import settings
from app.database.models import Base

engine = create_engine(settings.database_url, echo=False, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    """Dependency for providing a database session to route handlers."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


__all__ = [
    "engine",
    "SessionLocal",
    "get_db",
    "Base",
]
