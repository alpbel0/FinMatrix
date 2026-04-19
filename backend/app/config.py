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

    # LLM Settings for Agents
    query_understanding_model: str = "google/gemini-2.5-pro"
    query_rewrite_model: str = "google/gemma-4-26b-a4b-it:free"  # Same model, optional usage
    response_agent_model: str = "google/gemini-3.1-flash-lite-preview"
    query_classifier_model: str = "google/gemini-2.0-flash-lite-001"
    query_classifier_fallback_model: str = "google/gemma-4-26b-a4b-it:free"
    orchestrator_model: str = "google/gemma-4-31b-it"
    llm_timeout: float = 60.0
    llm_max_tokens: int = 2048
    llm_temperature: float = 0.7
    chat_memory_window: int = 5  # Last N messages for context

    # Retrieval sufficiency criteria (multi-factor)
    min_chunks_for_context: int = 1  # At least 1 chunk
    max_chunk_distance: float = 1.5  # L2 distance threshold (lower = better match)
    # IMPORTANT: L2 distance'te düşük değer daha iyi. max_chunk_distance üst sınır.
    min_total_context_chars: int = 500  # Minimum total content length

    # Query rewrite settings
    enable_query_rewrite: bool = False  # Default: disabled, truly optional


@lru_cache
def get_settings() -> Settings:
    return Settings()
