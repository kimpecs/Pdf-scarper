"""
SQLAlchemy engine + session factory.

Usage:
    from app.services.db.session import get_session, engine

    with get_session() as session:
        parts = session.query(Part).filter_by(published=True).all()
"""

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.utils.config import settings
from app.services.db.orm_models import Base

# Create engine lazily so import never crashes before config is ready
_engine = None
_SessionLocal = None


def _get_engine():
    global _engine
    if _engine is None:
        db_url = settings.active_database_url
        connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}
        _engine = create_engine(
            db_url,
            connect_args=connect_args,
            pool_pre_ping=True,
            echo=settings.DEBUG,
        )
    return _engine


def _get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=_get_engine(),
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )
    return _SessionLocal


@contextmanager
def get_session() -> Session:
    """Context-manager that yields a Session and handles commit/rollback."""
    factory = _get_session_factory()
    session: Session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def create_all_tables():
    """Create all ORM tables if they don't exist yet (dev / initial setup)."""
    Base.metadata.create_all(bind=_get_engine())


# Expose the factory callable for the audit middleware
session_factory = _get_session_factory
