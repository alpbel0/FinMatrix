from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str
    chroma_host: str = "localhost"
    chroma_port: int = 8001
    openrouter_api_key: str = ""
    telegram_bot_token: str = ""
    jwt_secret_key: str = "dev-secret"
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 60
    cors_origins: str = "http://localhost:3000"
    log_level: str = "INFO"

    # PDF Download Settings
    pdf_storage_path: str = "data/pdfs"  # Relative to backend directory
    pdf_max_downloads_per_run: int = 50
    pdf_download_timeout: float = 30.0
    pdf_transient_retry_count: int = 2  # ONLY for transient network errors within single run


@lru_cache
def get_settings() -> Settings:
    return Settings()
