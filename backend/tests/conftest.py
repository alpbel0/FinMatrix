"""Shared pytest fixtures for FinMatrix tests.

Uses real PostgreSQL test DB (finmatrix_test) with Alembic migrations.
No SQLAlchemy session mocking — all DB operations hit real tables.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncGenerator
from concurrent.futures import ThreadPoolExecutor

import pytest
from alembic import command
from alembic.config import Config
from httpx import AsyncClient, ASGITransport
from sqlalchemy import make_url, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.main import app
from app.dependencies import get_db_session
from app.config import get_settings

settings = get_settings()

# Build test database URL
url = make_url(settings.database_url)
test_db_name = f"{url.database}_test"

# Sync URL for Alembic (alembic does not support +asyncpg)
TEST_SYNC_URL = (
    f"postgresql://{url.username}:{url.password}@{url.host}:{url.port}/{test_db_name}"
)
# Async URL for SQLAlchemy sessions
TEST_ASYNC_URL = (
    f"postgresql+asyncpg://{url.username}:{url.password}@{url.host}:{url.port}/{test_db_name}"
)

ALEMBIC_INI_PATH = os.path.join(os.path.dirname(__file__), "..", "alembic.ini")


@pytest.fixture(scope="function")
async def test_engine():
    """Create test database engine, run Alembic migrations, tear down after."""
    engine = create_async_engine(TEST_ASYNC_URL, echo=False, pool_pre_ping=True)

    # Ensure test DB exists (sync operation using standard psycopg2 engine)
    from sqlalchemy import create_engine as create_sync_engine

    sync_engine = create_sync_engine(
        TEST_SYNC_URL,
        echo=False,
        pool_pre_ping=True,
        isolation_level="AUTOCOMMIT",
    )
    with sync_engine.connect() as conn:
        result = conn.execute(
            text(f"SELECT 1 FROM pg_database WHERE datname = '{test_db_name}'")
        )
        if result.scalar() is None:
            conn.execute(text(f"CREATE DATABASE {test_db_name}"))
    sync_engine.dispose()

    # Run Alembic migrations to latest revision (in a separate thread so
    # alembic's own asyncio.run() inside env.py does not conflict with pytest-asyncio)
    alembic_cfg = Config(ALEMBIC_INI_PATH)
    alembic_cfg.set_main_option("sqlalchemy.url", TEST_SYNC_URL)

    try:
        await asyncio.to_thread(command.upgrade, alembic_cfg, "head")
        print("[conftest] Alembic upgrade completed")
    except Exception as exc:
        print(f"[conftest] Alembic upgrade FAILED: {exc}")
        raise

    yield engine

    # Drop all tables via Alembic downgrade to base
    try:
        await asyncio.to_thread(command.downgrade, alembic_cfg, "base")
        print("[conftest] Alembic downgrade completed")
    except Exception as exc:
        print(f"[conftest] Alembic downgrade FAILED: {exc}")
    await engine.dispose()


@pytest.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Provide async database session for tests."""
    async_session_factory = async_sessionmaker(
        test_engine, expire_on_commit=False, class_=AsyncSession
    )
    async with async_session_factory() as session:
        yield session


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Provide HTTP client with overridden database dependency."""
    async def override_get_db_session():
        yield db_session

    app.dependency_overrides[get_db_session] = override_get_db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
