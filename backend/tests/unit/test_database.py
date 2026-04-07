"""Unit tests for app/database.py utilities."""

import pytest

from app.database import _to_async_database_url


class TestToAsyncDatabaseUrl:
    """Test _to_async_database_url conversion function."""

    def test_already_async_url_unchanged(self):
        """URL with asyncpg driver should remain unchanged."""
        url = "postgresql+asyncpg://user:pass@localhost:5432/db"
        result = _to_async_database_url(url)
        assert result == url

    def test_sync_url_converted_to_async(self):
        """postgresql:// URL should be converted to postgresql+asyncpg://."""
        url = "postgresql://user:pass@localhost:5432/db"
        result = _to_async_database_url(url)
        assert result == "postgresql+asyncpg://user:pass@localhost:5432/db"

    def test_other_schemes_unchanged(self):
        """Non-postgreSQL URLs should remain unchanged."""
        url = "sqlite:///test.db"
        result = _to_async_database_url(url)
        assert result == url

    def test_mysql_url_unchanged(self):
        """MySQL URLs should remain unchanged."""
        url = "mysql://user:pass@localhost/db"
        result = _to_async_database_url(url)
        assert result == url

    def test_url_with_query_params(self):
        """URL with query parameters should be converted correctly."""
        url = "postgresql://user:pass@localhost:5432/db?sslmode=require"
        result = _to_async_database_url(url)
        assert result == "postgresql+asyncpg://user:pass@localhost:5432/db?sslmode=require"


# Note: check_database_connection tests are covered by integration tests
# Global engine causes test isolation issues in unit test context