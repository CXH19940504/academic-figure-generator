"""FastAPI dependency injection providers — personal-use (no auth)."""

import logging
from collections.abc import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# ---------------------------------------------------------------------------
# Database (MySQL via asyncmy, or SQLite via aiosqlite)
# ---------------------------------------------------------------------------

_is_sqlite = settings.DATABASE_URL.startswith("sqlite")

_engine_kwargs: dict = dict(
    echo=settings.DEBUG,
    pool_pre_ping=True,
)
if _is_sqlite:
    _engine_kwargs["connect_args"] = {"timeout": 10}

_engine = create_async_engine(settings.DATABASE_URL, **_engine_kwargs)


if _is_sqlite:

    @event.listens_for(_engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        """Enable WAL mode and tune SQLite for concurrent access."""
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()


_AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=_engine,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async SQLAlchemy session, closing it after the request."""
    async with _AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_async_session_factory():
    """Return the async session factory for use outside of FastAPI DI."""
    return _AsyncSessionLocal
