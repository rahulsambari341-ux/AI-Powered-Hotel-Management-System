"""
Database connection setup.

This module creates:
- `engine`: the SQLAlchemy connection to MySQL.
- `SessionLocal`: a factory for database sessions (one per request).
- `Base`: the declarative base class that all ORM models (Phase 2) will inherit from.
- `get_db()`: a FastAPI dependency that yields a session and closes it afterward.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import settings

# `pool_pre_ping=True` makes SQLAlchemy test the connection before using it,
# so we don't get stale-connection errors if MySQL restarts or idles out.
engine = create_engine(settings.database_url, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """
    FastAPI dependency. Opens a session, hands it to the endpoint,
    and guarantees it's closed afterward even if the endpoint raises.

    Usage in an endpoint:
        def my_route(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
