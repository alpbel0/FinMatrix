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

    # Chunking Settings
    chunk_target_tokens: int = 500  # ~500 token target chunk size
    chunk_overlap_tokens: int = 50  # ~50 token overlap between chunks
    chunk_max_per_run: int = 50  # Max PDFs to chunk per scheduler run
    min_chunk_chars: int = 50  # Minimum chars for meaningful chunk (boilerplate filter)
    min_alpha_ratio: float = 0.3  # Minimum alphanumeric ratio for meaningful content

    # Embedding Settings
    embedding_model: str = "openai/text-embedding-3-small"
    embedding_dimension: int = 1536
    embedding_batch_size: int = 100  # Chunks per OpenRouter API call
    embedding_timeout: float = 30.0
    embedding_retry_count: int = 2  # Transient error retry count
    embedding_max_per_run: int = 500  # Max chunks to embed per scheduler run
    chroma_collection_name: str = "kap_documents"


@lru_cache
def get_settings() -> Settings:
    return Settings()
