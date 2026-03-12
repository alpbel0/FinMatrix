"""
Test configuration and fixtures for FinMatrix backend.

This module provides pytest fixtures for:
- Async test client
- Test database engine and session
- Factory Boy integration for test data
"""

import asyncio
import os
from datetime import datetime, timedelta
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

# Set test environment before importing app
os.environ.setdefault("TEST_DATABASE_URL", "postgresql+asyncpg://finmatrix_test:finmatrix_test@test-db:5432/finmatrix_test")
os.environ.setdefault("DATABASE_URL", "postgresql://finmatrix:finmatrix@db:5432/finmatrix")
os.environ.setdefault("GOOGLE_API_KEY", "test-api-key")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-jwt-signing")


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def app():
    """Create FastAPI app for testing."""
    from app.main import app as fastapi_app
    return fastapi_app


@pytest_asyncio.fixture
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    """Create async test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac


# --- Database Fixtures ---

@pytest.fixture(scope="session")
def test_db_url() -> str:
    """Get test database URL from environment."""
    return os.getenv(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://finmatrix_test:finmatrix_test@test-db:5432/finmatrix_test"
    )


def _get_partition_ranges() -> list:
    """
    Generate partition ranges for stock_prices table.

    Creates monthly partitions for:
    - Past 3 months
    - Current month
    - Next 12 months

    Returns list of (partition_name, start_date, end_date) tuples.
    """
    partitions = []
    today = datetime.utcnow().date()

    # Past 3 months
    for i in range(3, 0, -1):
        month_date = today - timedelta(days=30 * i)
        start = month_date.replace(day=1)
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)

        partition_name = f"stock_prices_{start.year}_{start.month:02d}"
        partitions.append((partition_name, start.isoformat(), end.isoformat()))

    # Current month + next 12 months
    for i in range(13):
        month_date = today + timedelta(days=30 * i)
        start = month_date.replace(day=1)
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)

        partition_name = f"stock_prices_{start.year}_{start.month:02d}"
        partitions.append((partition_name, start.isoformat(), end.isoformat()))

    return partitions


@pytest_asyncio.fixture
async def test_engine(test_db_url: str):
    """
    Create async engine for test database.

    Creates all tables and necessary partitions for stock_prices.
    """
    from app.models import Base

    engine = create_async_engine(test_db_url, echo=False, pool_pre_ping=True)

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create partitions for stock_prices table
    async_session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session_factory() as session:
        # Create a DEFAULT partition for safety (catches any date)
        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS stock_prices_default
            PARTITION OF stock_prices DEFAULT;
        """))

        # Create monthly partitions
        partitions = _get_partition_ranges()
        for partition_name, start_date, end_date in partitions:
            try:
                await session.execute(text(f"""
                    CREATE TABLE IF NOT EXISTS {partition_name}
                    PARTITION OF stock_prices
                    FOR VALUES FROM ('{start_date}') TO ('{end_date}');
                """))
            except Exception:
                # Partition might already exist, ignore
                pass

        await session.commit()

    yield engine

    # Drop all tables after test
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def test_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """
    Create async session for each test.

    Each test gets a fresh session.
    """
    async_session_factory = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )

    async with async_session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def async_client_with_db(test_session: AsyncSession, app):
    """
    Create async test client with database session injected.

    Use this fixture when you need both HTTP client and DB access.
    """
    from app.dependencies import get_db

    async def override_get_db():
        yield test_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


# --- Helper Functions ---

def override_get_settings():
    """Override settings for testing."""
    from app.config import Settings
    return Settings(
        database_url="postgresql://finmatrix:finmatrix@db:5432/finmatrix",
        test_database_url="postgresql+asyncpg://finmatrix_test:finmatrix_test@test-db:5432/finmatrix_test",
        google_api_key="test-api-key",
        secret_key="test-secret-key-for-jwt-signing",
        debug=True,
    )