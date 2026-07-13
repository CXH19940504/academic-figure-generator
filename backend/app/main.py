"""FastAPI application factory — personal-use version."""

import logging
import re
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, text

from app.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.middleware import setup_middleware

_LOG_FILE = Path("/tmp/app_backend.log")

logging.basicConfig(
    level=logging.DEBUG if get_settings().DEBUG else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(_LOG_FILE, encoding="utf-8"),
    ],
)

logger = logging.getLogger(__name__)


def _ensure_database_exists(db_url: str) -> None:
    """Create the MySQL database if it does not already exist.

    Uses a temporary sync engine (pymysql) connecting without a database name,
    then issues CREATE DATABASE IF NOT EXISTS.
    """
    # Parse database name from URL: mysql+asyncmy://user:pass@host:port/dbname
    match = re.search(r"/([^/?]+)(?:\?|$)", db_url)
    if not match:
        return
    db_name = match.group(1)

    # Strip the database name to connect at server level
    base_url = re.sub(r"/([^/?]+)(\?|$)", r"/\2", db_url, count=1).rstrip("/")
    sync_url = base_url.replace("mysql+asyncmy://", "mysql+pymysql://", 1)

    try:
        sync_engine = create_engine(sync_url, isolation_level="AUTOCOMMIT")
        with sync_engine.connect() as conn:
            conn.execute(
                text(
                    f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
                    "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
            )
        sync_engine.dispose()
        logger.info("Database '%s' verified/created.", db_name)
    except Exception as exc:
        logger.warning("Could not auto-create database '%s': %s", db_name, exc)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup and shutdown logic."""
    logger.info("Starting up Academic Figure Generator API (personal-use)...")

    # Ensure MySQL database exists, then create tables
    settings = get_settings()
    try:
        from app.dependencies import _engine  # noqa: PLC0415
        from app.models import Base  # noqa: PLC0415

        _ensure_database_exists(settings.DATABASE_URL)

        async with _engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("MySQL database tables verified.")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Database setup failed (continuing): %s", exc)

    # Seed preset color schemes
    try:
        await _seed_preset_color_schemes()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Preset color scheme seeding failed (continuing): %s", exc)

    # Ensure data directories exist
    data_dir = Path(settings.DATA_DIR)
    (data_dir / "uploads").mkdir(parents=True, exist_ok=True)
    (data_dir / "figures").mkdir(parents=True, exist_ok=True)

    yield

    logger.info("Shutting down Academic Figure Generator API...")


async def _seed_preset_color_schemes() -> None:
    """Ensure system preset color schemes exist in the DB (idempotent)."""
    from sqlalchemy import select  # noqa: PLC0415

    from app.core.prompts.color_schemes import (  # noqa: PLC0415
        COLOR_SCHEME_DISPLAY_NAMES,
        DEFAULT_COLOR_SCHEME,
        PRESET_COLOR_SCHEMES,
    )
    from app.dependencies import get_async_session_factory  # noqa: PLC0415
    from app.models.color_scheme import ColorScheme  # noqa: PLC0415

    session_factory = get_async_session_factory()
    async with session_factory() as session:
        for slug, colors in PRESET_COLOR_SCHEMES.items():
            display_name = COLOR_SCHEME_DISPLAY_NAMES.get(slug, slug)
            existing = (
                await session.execute(
                    select(ColorScheme.id).where(
                        ColorScheme.type == "preset",
                        ColorScheme.name == display_name,
                    )
                )
            ).scalar_one_or_none()
            if existing is not None:
                continue

            session.add(
                ColorScheme(
                    name=display_name,
                    type="preset",
                    colors=colors,
                    is_default=(slug == DEFAULT_COLOR_SCHEME),
                )
            )

        await session.commit()


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Academic Figure Generator API",
        version="0.2.0",
        description="AI-powered scientific paper illustration service (personal-use)",
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        lifespan=lifespan,
    )

    # Middleware (CORS, request logging)
    setup_middleware(app)

    # Exception handlers
    register_exception_handlers(app)

    # Routers
    _include_routers(app, settings.API_V1_PREFIX)

    # Static file serving for generated figures and uploads
    data_dir = Path(settings.DATA_DIR)
    data_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/data", StaticFiles(directory=str(data_dir)), name="data")

    return app


def _include_routers(app: FastAPI, prefix: str) -> None:
    """Register all v1 API routers."""
    router_modules = [
        ("app.api.v1.health", "router"),
        ("app.api.v1.projects", "router"),
        ("app.api.v1.templates", "router"),
        ("app.api.v1.documents", "router"),
        ("app.api.v1.prompts", "router"),
        ("app.api.v1.images", "router"),
        ("app.api.v1.color_schemes", "router"),
    ]

    for module_path, attr in router_modules:
        try:
            import importlib  # noqa: PLC0415

            module = importlib.import_module(module_path)
            router = getattr(module, attr)
            app.include_router(router, prefix=prefix)
            logger.debug("Registered router: %s", module_path)
        except (ImportError, AttributeError) as exc:
            logger.warning("Skipping router %s: %s", module_path, exc)


app = create_app()
