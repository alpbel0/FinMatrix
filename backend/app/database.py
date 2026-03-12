"""
Database configuration for FinMatrix.

Provides async SQLAlchemy engine, session factory, and declarative base
for ORM models and Alembic migrations.
"""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


def get_async_database_url(url: str) -> str:
    """
    Convert PostgreSQL URL to async format.

    Transforms postgresql:// to postgresql+asyncpg:// for async support.
    """
    if url.startswith("postgresql://") and "+asyncpg" not in url:
        return url.replace("postgresql://", "postgresql+asyncpg://")
    return url


# Async engine configuration
engine = create_async_engine(
    get_async_database_url(settings.effective_database_url),
    pool_size=settings.database_pool_size,
    echo=settings.debug,
)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""

    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency that provides an async database session.

    Yields an async session and ensures proper cleanup after use.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()