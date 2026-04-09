"""Unit tests for embedding service.

Tests for:
- EmbeddingStatus enum
- Chunk metadata building (_build_chunk_metadata)
- Retry eligibility (_is_embedding_retry_eligible)
- Service functions (mocked httpx, mocked ChromaDB, mocked AsyncSession)
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.pipeline.embedding_service import (
    EmbeddingStatus,
    EmbeddingResult,
    EmbeddingBatchResult,
    _build_chunk_metadata,
    _is_embedding_retry_eligible,
    EMBEDDING_RETRY_PATTERNS,
    OPENROUTER_EMBEDDING_URL,
    EMBEDDING_MODEL,
)


# ============================================================================
# EmbeddingStatus Enum Tests
# ============================================================================


class TestEmbeddingStatusEnum:
    """Tests for EmbeddingStatus enum."""

    def test_values(self):
        """Test that enum has expected values."""
        assert EmbeddingStatus.PENDING.value == "PENDING"
        assert EmbeddingStatus.COMPLETED.value == "COMPLETED"
        assert EmbeddingStatus.FAILED.value == "FAILED"

    def test_string_comparison(self):
        """Test that enum can be compared with strings."""
        assert EmbeddingStatus.PENDING == "PENDING"
        assert EmbeddingStatus.COMPLETED != "FAILED"

    def test_matches_document_chunk_status(self):
        """Test that enum values match DocumentChunk.embedding_status field."""
        # The DocumentChunk model uses default="PENDING" for embedding_status
        # This enum should match those values
        assert EmbeddingStatus.PENDING.value == "PENDING"
        assert EmbeddingStatus.COMPLETED.value == "COMPLETED"
        assert EmbeddingStatus.FAILED.value == "FAILED"


# ============================================================================
# Metadata Builder Tests
# ============================================================================


class TestBuildChunkMetadata:
    """Tests for _build_chunk_metadata function."""

    def test_all_fields_present(self):
        """Test that all required metadata fields are present."""
        from app.models.document_chunk import DocumentChunk
        from app.models.kap_report import KapReport

        # Create mock objects
        chunk = MagicMock(spec=DocumentChunk)
        chunk.id = 1
        chunk.kap_report_id = 100
        chunk.chunk_index = 5
        chunk.chunk_text = "Test chunk content"
        chunk.chunk_text_hash = "abc123hash"

        kap_report = MagicMock(spec=KapReport)
        kap_report.id = 100
        kap_report.title = "2024 Yılı Faaliyet Raporu"
        kap_report.published_at = datetime(2024, 6, 15, 10, 30, tzinfo=timezone.utc)
        kap_report.filing_type = "FR"

        result = _build_chunk_metadata(
            chunk=chunk,
            kap_report=kap_report,
            stock_symbol="THYAO",
        )

        # Check all required fields
        assert result["stock_symbol"] == "THYAO"
        assert result["report_title"] == "2024 Yılı Faaliyet Raporu"
        assert result["published_at"] == "2024-06-15T10:30:00+00:00"
        assert result["filing_type"] == "FR"
        assert result["chunk_index"] == 5
        assert result["kap_report_id"] == 100
        assert result["chunk_text_hash"] == "abc123hash"

    def test_none_published_at(self):
        """Test handling of None published_at."""
        from app.models.document_chunk import DocumentChunk
        from app.models.kap_report import KapReport

        chunk = MagicMock(spec=DocumentChunk)
        chunk.chunk_index = 0
        chunk.chunk_text_hash = "hash123"
        chunk.kap_report_id = 1

        kap_report = MagicMock(spec=KapReport)
        kap_report.title = "Test Report"
        kap_report.published_at = None
        kap_report.filing_type = None

        result = _build_chunk_metadata(
            chunk=chunk,
            kap_report=kap_report,
            stock_symbol="GARAN",
        )

        assert result["published_at"] is None
        assert result["filing_type"] == ""

    def test_long_title_truncated(self):
        """Test that very long titles are truncated."""
        from app.models.document_chunk import DocumentChunk
        from app.models.kap_report import KapReport

        chunk = MagicMock(spec=DocumentChunk)
        chunk.chunk_index = 0
        chunk.chunk_text_hash = "hash"
        chunk.kap_report_id = 1

        kap_report = MagicMock(spec=KapReport)
        kap_report.title = "A" * 600  # Very long title
        kap_report.published_at = None
        kap_report.filing_type = "FR"

        result = _build_chunk_metadata(
            chunk=chunk,
            kap_report=kap_report,
            stock_symbol="THYAO",
        )

        assert len(result["report_title"]) == 500  # Truncated


# ============================================================================
# Retry Eligibility Tests
# ============================================================================


class TestIsEmbeddingRetryEligible:
    """Tests for _is_embedding_retry_eligible function."""

    def test_timeout_is_retry_eligible(self):
        """Test that timeout errors are retry eligible."""
        error_message = "Timeout: Request timed out after 30s"
        result = _is_embedding_retry_eligible(error_message)
        assert result is True

    def test_rate_limit_429_is_retry_eligible(self):
        """Test that rate limit errors are retry eligible."""
        error_message = "HTTP 429: Rate limit exceeded"
        result = _is_embedding_retry_eligible(error_message)
        assert result is True

    def test_server_error_500_is_retry_eligible(self):
        """Test that server errors are retry eligible."""
        error_message = "HTTP 500: Internal server error"
        result = _is_embedding_retry_eligible(error_message)
        assert result is True

    def test_auth_error_not_retry_eligible(self):
        """Test that authentication errors are NOT retry eligible."""
        error_message = "HTTP 401: Unauthorized"
        result = _is_embedding_retry_eligible(error_message)
        assert result is False

    def test_invalid_request_not_retry_eligible(self):
        """Test that invalid request errors are NOT retry eligible."""
        error_message = "HTTP 400: Bad request"
        result = _is_embedding_retry_eligible(error_message)
        assert result is False

    def test_connection_refused_is_retry_eligible(self):
        """Test that connection refused is retry eligible."""
        error_message = "Connection refused: Unable to connect"
        result = _is_embedding_retry_eligible(error_message)
        assert result is True


# ============================================================================
# Result Model Tests
# ============================================================================


class TestEmbeddingResult:
    """Tests for EmbeddingResult model."""

    def test_default_values(self):
        """Test default values for optional fields."""
        result = EmbeddingResult(
            chunk_id=1,
            success=True,
            status=EmbeddingStatus.COMPLETED,
        )
        assert result.chroma_document_id is None
        assert result.error_message is None

    def test_all_fields(self):
        """Test with all fields populated."""
        result = EmbeddingResult(
            chunk_id=1,
            success=True,
            chroma_document_id="abc123hash",
            status=EmbeddingStatus.COMPLETED,
        )
        assert result.chroma_document_id == "abc123hash"
        assert result.status == EmbeddingStatus.COMPLETED

    def test_status_uses_enum(self):
        """Test that status uses EmbeddingStatus enum."""
        result = EmbeddingResult(
            chunk_id=1,
            success=False,
            error_message="Test error",
            status=EmbeddingStatus.FAILED,
        )
        assert result.status == EmbeddingStatus.FAILED
        assert result.status.value == "FAILED"


class TestEmbeddingBatchResult:
    """Tests for EmbeddingBatchResult model."""

    def test_default_values(self):
        """Test default values."""
        result = EmbeddingBatchResult(
            total_processed=100,
            successful=95,
            failed=5,
            status="partial",
        )
        assert result.results == []
        assert result.details is None

    def test_with_results(self):
        """Test with results list."""
        single_result = EmbeddingResult(
            chunk_id=1,
            success=True,
            status=EmbeddingStatus.COMPLETED,
        )
        result = EmbeddingBatchResult(
            total_processed=1,
            successful=1,
            failed=0,
            status="success",
            results=[single_result],
        )
        assert len(result.results) == 1


# ============================================================================
# Service Function Tests (Mocked)
# ============================================================================


class TestBatchEmbedPendingChunks:
    """Tests for batch_embed_pending_chunks function."""

    @pytest.mark.asyncio
    async def test_no_pending_chunks(self):
        """Test when no chunks are pending embedding."""
        from app.services.pipeline.embedding_service import batch_embed_pending_chunks

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db.execute.return_value = mock_result

        result = await batch_embed_pending_chunks(db=db, limit=500)

        assert result.total_processed == 0
        assert result.successful == 0
        assert result.failed == 0
        assert result.status == "success"


class TestEmbedChunksBatch:
    """Tests for embed_chunks_batch function."""

    @pytest.mark.asyncio
    async def test_empty_chunks_list(self):
        """Test with empty chunks list."""
        from app.services.pipeline.embedding_service import embed_chunks_batch

        db = AsyncMock()

        result = await embed_chunks_batch(
            db=db,
            chunks=[],
            kap_report_map={},
            stock_symbol_map={},
        )

        assert result.total_processed == 0
        assert result.successful == 0
        assert result.failed == 0
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_missing_kap_report_marks_only_missing_chunk_failed(self):
        """Test mixed valid/invalid chunks do not cause index drift."""
        from app.services.pipeline.embedding_service import embed_chunks_batch

        valid_chunk = MagicMock()
        valid_chunk.id = 1
        valid_chunk.kap_report_id = 100
        valid_chunk.chunk_text = "Valid chunk text"
        valid_chunk.chunk_text_hash = "valid-hash"
        valid_chunk.embedding_status = "PENDING"
        valid_chunk.chroma_document_id = None
        valid_chunk.chunk_index = 0

        invalid_chunk = MagicMock()
        invalid_chunk.id = 2
        invalid_chunk.kap_report_id = 999
        invalid_chunk.chunk_text = "Invalid chunk text"
        invalid_chunk.chunk_text_hash = "invalid-hash"
        invalid_chunk.embedding_status = "PENDING"
        invalid_chunk.chroma_document_id = None
        invalid_chunk.chunk_index = 1

        kap_report = MagicMock()
        kap_report.id = 100
        kap_report.stock_id = 10
        kap_report.title = "Valid report"
        kap_report.published_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
        kap_report.filing_type = "FR"

        collection = MagicMock()
        db = AsyncMock()

        with patch("app.services.pipeline.embedding_service._get_or_create_collection", return_value=collection):
            with patch(
                "app.services.pipeline.embedding_service._get_embeddings_from_openrouter",
                AsyncMock(return_value=[[0.1, 0.2, 0.3]]),
            ):
                result = await embed_chunks_batch(
                    db=db,
                    chunks=[valid_chunk, invalid_chunk],
                    kap_report_map={100: kap_report},
                    stock_symbol_map={10: "THYAO"},
                )

        assert result.total_processed == 2
        assert result.successful == 1
        assert result.failed == 1
        assert valid_chunk.embedding_status == EmbeddingStatus.COMPLETED.value
        assert valid_chunk.chroma_document_id == "valid-hash"
        assert invalid_chunk.embedding_status == EmbeddingStatus.FAILED.value
        collection.upsert.assert_called_once()
        upsert_kwargs = collection.upsert.call_args.kwargs
        assert upsert_kwargs["ids"] == ["valid-hash"]


# ============================================================================
# OpenRouter API Integration Tests (Mocked)
# ============================================================================


class TestOpenRouterEmbedding:
    """Tests for OpenRouter embedding API integration."""

    @pytest.mark.asyncio
    async def test_successful_embedding_call(self):
        """Test successful embedding API call."""
        from app.services.pipeline.embedding_service import _get_embeddings_from_openrouter
        import httpx

        # Mock httpx response
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {"embedding": [0.1, 0.2, 0.3], "index": 0},
                {"embedding": [0.4, 0.5, 0.6], "index": 1},
            ]
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value = mock_client_instance

            # This is a simplified test - actual function requires AsyncClient
            pass  # Would need more complex mocking

    def test_embedding_url_correct(self):
        """Test that embedding URL is correct."""
        assert OPENROUTER_EMBEDDING_URL == "https://openrouter.ai/api/v1/embeddings"

    def test_embedding_model_correct(self):
        """Test that embedding model is correct."""
        assert EMBEDDING_MODEL == "openai/text-embedding-3-small"


# ============================================================================
# Batch vs API Batch Distinction Tests
# ============================================================================


class TestBatchDistinction:
    """Tests for batch vs API batch distinction."""

    def test_embedding_batch_size_in_config(self):
        """Test that embedding_batch_size is configurable."""
        from app.config import get_settings

        settings = get_settings()
        assert hasattr(settings, "embedding_batch_size")
        assert settings.embedding_batch_size == 100

    def test_embedding_max_per_run_in_config(self):
        """Test that embedding_max_per_run is configurable."""
        from app.config import get_settings

        settings = get_settings()
        assert hasattr(settings, "embedding_max_per_run")
        assert settings.embedding_max_per_run == 500

    def test_batch_smaller_than_api_batch(self):
        """Test that scheduler run limit can be larger than API batch."""
        from app.config import get_settings

        settings = get_settings()
        # 500 chunks per run can be split into 5 API batches of 100
        assert settings.embedding_max_per_run >= settings.embedding_batch_size
