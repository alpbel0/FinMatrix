from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional
from functools import lru_cache
import json


class Settings(BaseSettings):
    # Database Configuration
    database_url: str
    database_pool_size: int = 5
    test_database_url: Optional[str] = None

    # API Keys
    google_api_key: str
    openai_api_key: Optional[str] = None

    # ChromaDB
    chroma_host: str = "localhost"
    chroma_port: int = 8001

    # Telegram
    telegram_bot_token: Optional[str] = None

    # Security
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Application
    app_name: str = "FinMatrix"
    app_version: str = "0.1.0"
    debug: bool = False
    log_level: str = "INFO"
    cors_origins: str = '["http://localhost:3000"]'

    @property
    def cors_origins_list(self) -> List[str]:
        return json.loads(self.cors_origins)

    @property
    def effective_database_url(self) -> str:
        """Return test database URL if set, otherwise production URL."""
        return self.test_database_url or self.database_url

    # Pydantic v2 configuration
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        env_file_encoding="utf-8"
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()