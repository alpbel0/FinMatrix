"""Unit tests for app/config.py Settings class."""

import pytest

from app.config import Settings, get_settings


class TestSettingsDefaults:
    """Test default values in Settings class."""

    def test_jwt_algorithm_default(self):
        """JWT algorithm should default to HS256."""
        settings = Settings(database_url="postgresql://localhost/test")
        assert settings.jwt_algorithm == "HS256"

    def test_jwt_expiration_minutes_default(self):
        """JWT expiration should default to 60 minutes."""
        settings = Settings(database_url="postgresql://localhost/test")
        assert settings.jwt_expiration_minutes == 60

    def test_log_level_default(self):
        """Log level should default to INFO."""
        settings = Settings(database_url="postgresql://localhost/test")
        assert settings.log_level == "INFO"

    def test_cors_origins_has_value(self):
        """CORS origins should have a value (from env or default)."""
        settings = Settings(database_url="postgresql://localhost/test")
        assert settings.cors_origins  # Should have some value
        assert isinstance(settings.cors_origins, str)

    def test_chroma_defaults(self):
        """ChromaDB settings should have defaults."""
        settings = Settings(database_url="postgresql://localhost/test")
        assert settings.chroma_host == "localhost"
        assert settings.chroma_port == 8001


class TestSettingsRequiredFields:
    """Test that required fields are enforced."""

    def test_database_url_present(self):
        """Database URL should be present (from .env or explicit)."""
        settings = Settings()
        assert settings.database_url is not None
        assert settings.database_url.startswith("postgresql")

    def test_settings_with_explicit_database_url(self):
        """Settings should accept explicit database_url overriding .env."""
        settings = Settings(database_url="postgresql://user:pass@host:5432/db")
        assert settings.database_url == "postgresql://user:pass@host:5432/db"


class TestSettingsOptionalFields:
    """Test optional fields can be set."""

    def test_openrouter_api_key_optional(self):
        """OpenRouter API key should be optional."""
        settings = Settings(
            database_url="postgresql://localhost/test",
            openrouter_api_key="sk-or-test"
        )
        assert settings.openrouter_api_key == "sk-or-test"

    def test_telegram_bot_token_optional(self):
        """Telegram bot token should be optional."""
        settings = Settings(
            database_url="postgresql://localhost/test",
            telegram_bot_token="123:ABC"
        )
        assert settings.telegram_bot_token == "123:ABC"

    def test_jwt_secret_key_optional(self):
        """JWT secret key should be optional with default."""
        settings = Settings(
            database_url="postgresql://localhost/test",
            jwt_secret_key="my-secret"
        )
        assert settings.jwt_secret_key == "my-secret"


class TestGetSettings:
    """Test get_settings function."""

    def test_get_settings_returns_settings(self):
        """get_settings should return a Settings instance."""
        settings = get_settings()
        assert isinstance(settings, Settings)

    def test_get_settings_cached(self):
        """get_settings should return cached instance (lru_cache)."""
        settings1 = get_settings()
        settings2 = get_settings()
        assert settings1 is settings2