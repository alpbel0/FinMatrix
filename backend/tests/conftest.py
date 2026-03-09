"""
Test configuration and fixtures for FinMatrix backend.

This module provides pytest fixtures for:
- Async test client
- Test database (when models are implemented)
- Factory Boy integration for test data
"""

import asyncio
import os
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

# Set test environment before importing app
os.environ.setdefault("TEST_DATABASE_URL", "postgresql+asyncpg://finmatrix_test:finmatrix_test@localhost:5434/finmatrix_test")
os.environ.setdefault("DATABASE_URL", "postgresql://finmatrix:finmatrix@localhost:5433/finmatrix")
os.environ.setdefault("GOOGLE_API_KEY", "test-api-key")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-jwt-signing")


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
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


# --- Database Fixtures (ready for when models are implemented) ---

# These fixtures will be activated when database models are added.
# The test database container should be started with:
#   docker-compose -f docker-compose.test.yml up -d

@pytest.fixture(scope="session")
def test_db_url() -> str:
    """Get test database URL from environment."""
    return os.getenv(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://finmatrix_test:finmatrix_test@localhost:5434/finmatrix_test"
    )


# Note: The following fixtures will be uncommented when database.py is created
#
# from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
# from app.models import Base
#
# @pytest_asyncio.fixture(scope="session")
# async def test_engine(test_db_url):
#     """Create async engine for test database."""
#     engine = create_async_engine(test_db_url, echo=False)
#     async with engine.begin() as conn:
#         await conn.run_sync(Base.metadata.create_all)
#     yield engine
#     async with engine.begin() as conn:
#         await conn.run_sync(Base.metadata.drop_all)
#     await engine.dispose()
#
#
# @pytest_asyncio.fixture
# async def test_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
#     """Create async session for each test with rollback."""
#     async_session = async_sessionmaker(test_engine, expire_on_commit=False)
#     async with async_session() as session:
#         async with session.begin():
#             yield session
#             await session.rollback()


# --- Helper Functions ---

def override_get_settings():
    """Override settings for testing."""
    from app.config import Settings
    return Settings(
        database_url="postgresql://finmatrix:finmatrix@localhost:5433/finmatrix",
        test_database_url="postgresql+asyncpg://finmatrix_test:finmatrix_test@localhost:5434/finmatrix_test",
        google_api_key="test-api-key",
        secret_key="test-secret-key-for-jwt-signing",
        debug=True,
    )