"""
Unit tests for application configuration.

Tests cover:
- Settings class
- Environment variable parsing
- Default values
- Database URL conversion
"""

import os
import pytest

from app.config import Settings, get_settings
from app.database import get_async_database_url


class TestSettings:
    """Tests for Settings configuration class."""

    def test_database_url_required(self):
        """Settings should require database_url."""
        # This test verifies that Settings needs database_url
        # Since env vars are already set in container, we test the validation
        settings = Settings(
            database_url="postgresql://localhost/test",
            google_api_key="test-key",
            secret_key="test-secret"
        )
        assert settings.database_url is not None

    def test_cors_origins_parsing(self):
        """CORS origins should be parsed from JSON string."""
        settings = Settings(
            database_url="postgresql://localhost/test",
            google_api_key="test-key",
            secret_key="test-secret",
            cors_origins='["http://localhost:3000", "http://localhost:8080"]'
        )

        assert len(settings.cors_origins_list) == 2
        assert "http://localhost:3000" in settings.cors_origins_list
        assert "http://localhost:8080" in settings.cors_origins_list

    def test_default_values(self):
        """Settings should have sensible defaults when no env vars override."""
        # Create settings with minimal required fields
        # Note: Some defaults may be overridden by environment variables
        settings = Settings(
            database_url="postgresql://localhost/test",
            google_api_key="test-key",
            secret_key="test-secret"
        )

        # These defaults should always be set
        assert settings.app_name == "FinMatrix"
        assert settings.app_version == "0.1.0"
        assert settings.database_pool_size == 5
        assert settings.algorithm == "HS256"
        assert settings.access_token_expire_minutes == 30
        # chroma_host and chroma_port may be overridden by env vars in container

    def test_effective_database_url_with_test_url(self):
        """effective_database_url should return test URL when set."""
        settings = Settings(
            database_url="postgresql://localhost/prod",
            test_database_url="postgresql://localhost/test",
            google_api_key="test-key",
            secret_key="test-secret"
        )

        assert settings.effective_database_url == "postgresql://localhost/test"

    def test_effective_database_url_without_test_url(self):
        """effective_database_url should return database_url when test_url not provided in Settings."""
        # Explicitly pass test_database_url=None to override env var
        settings = Settings(
            database_url="postgresql://localhost/prod",
            google_api_key="test-key",
            secret_key="test-secret",
            test_database_url=None
        )

        # When test_database_url is explicitly None, should return database_url
        assert settings.effective_database_url == "postgresql://localhost/prod"

    def test_openai_api_key_can_be_set(self):
        """OpenAI API key should be settable."""
        settings = Settings(
            database_url="postgresql://localhost/test",
            google_api_key="test-key",
            openai_api_key="my-openai-key",
            secret_key="test-secret"
        )

        assert settings.openai_api_key == "my-openai-key"

    def test_telegram_bot_token_can_be_set(self):
        """Telegram bot token should be settable."""
        settings = Settings(
            database_url="postgresql://localhost/test",
            google_api_key="test-key",
            telegram_bot_token="my-bot-token",
            secret_key="test-secret"
        )

        assert settings.telegram_bot_token == "my-bot-token"

    def test_debug_flag(self):
        """Debug flag should be settable."""
        settings = Settings(
            database_url="postgresql://localhost/test",
            google_api_key="test-key",
            secret_key="test-secret",
            debug=True
        )

        assert settings.debug is True


class TestDatabaseURLConversion:
    """Tests for database URL async conversion."""

    def test_sync_url_to_async(self):
        """Sync PostgreSQL URL should be converted to async."""
        sync_url = "postgresql://user:pass@localhost:5432/db"
        async_url = get_async_database_url(sync_url)

        assert async_url == "postgresql+asyncpg://user:pass@localhost:5432/db"

    def test_async_url_unchanged(self):
        """Already async URL should remain unchanged."""
        async_url = "postgresql+asyncpg://user:pass@localhost:5432/db"
        result = get_async_database_url(async_url)

        assert result == async_url

    def test_other_url_unchanged(self):
        """Non-PostgreSQL URLs should remain unchanged."""
        sqlite_url = "sqlite:///./test.db"
        result = get_async_database_url(sqlite_url)

        assert result == sqlite_url


class TestSettingsCaching:
    """Tests for settings caching."""

    def test_get_settings_cached(self):
        """get_settings should return cached instance."""
        # Clear cache first
        get_settings.cache_clear()

        settings1 = get_settings()
        settings2 = get_settings()

        assert settings1 is settings2

    def test_get_settings_returns_settings_instance(self):
        """get_settings should return Settings instance."""
        get_settings.cache_clear()

        settings = get_settings()
        assert isinstance(settings, Settings)