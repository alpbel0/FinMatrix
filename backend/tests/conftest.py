"""Shared pytest fixtures for FinMatrix tests."""

import pytest
from collections.abc import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlalchemy import make_url
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.main import app
from app.database import Base
from app.dependencies import get_db_session
from app.config import get_settings

settings = get_settings()

# Build test database URL
url = make_url(settings.database_url)
test_db_name = f"{url.database}_test"

# Construct async test URL directly with credentials
TEST_ASYNC_URL = (
    f"postgresql+asyncpg://{url.username}:{url.password}@{url.host}:{url.port}/{test_db_name}"
)


@pytest.fixture(scope="function")
async def test_engine():
    """Create test database engine, clean up after each test."""
    engine = create_async_engine(TEST_ASYNC_URL, echo=False, pool_pre_ping=True)

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Drop tables after test
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Provide async database session for tests."""
    async_session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
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