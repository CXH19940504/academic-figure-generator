"""Database helpers — MySQL version."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings


def get_sync_engine():
    """Get sync engine for scripts (uses pymysql)."""
    settings = get_settings()
    sync_url = settings.DATABASE_URL.replace(
        "mysql+asyncmy://", "mysql+pymysql://", 1
    )
    return create_engine(sync_url, pool_pre_ping=True)


def get_sync_session():
    """Get sync session factory for scripts."""
    engine = get_sync_engine()
    return sessionmaker(bind=engine)
