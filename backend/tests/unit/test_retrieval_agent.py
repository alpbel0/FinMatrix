"""Unit tests for retrieval agent.

Tests:
- Sufficiency criteria (multi-factor)
- Source item preparation
- Filing type filtering
- Chunk conversion
"""

import pytest
from unittest.mock import MagicMock, patch

from app.schemas.enums import DocumentType
from app.schemas.chat import QueryUnderstandingResult, RetrievalAgentResult
from app.services.agents.retrieval_agent import (
    _chunk_to_dict,
    check_sufficient_context,
    prepare_source_items,
    run_retrieval,
)


class TestCheckSufficientContext:
    """Tests for check_sufficient_context function."""

    def test_empty_chunks(self):
        """Test empty chunks returns insufficient."""
        has_sufficient, confidence, total_chars = check_sufficient_context([])
        assert has_sufficient is False
        assert confidence == 0.0
        assert total_chars == 0

    def test_single_good_chunk(self):
        """Test single good chunk."""
        chunks = [
            {"score": 0.5, "chunk_text": "x" * 600}  # Good distance, enough chars
        ]
        has_sufficient, confidence, total_chars = check_sufficient_context(chunks)
        assert has_sufficient is True
        assert total_chars == 600

    def test_high_distance_chunk(self):
        """Test chunk with high distance (low similarity)."""
        chunks = [
            {"score": 0.9, "chunk_text": "x" * 600}  # High distance > 0.7
        ]
        has_sufficient, confidence, total_chars = check_sufficient_context(chunks)
        assert has_sufficient is False

    def test_low_char_count(self):
        """Test chunk with low character count."""
        chunks = [
            {"score": 0.5, "chunk_text": "x" * 100}  # Too short < 500
        ]
        has_sufficient, confidence, total_chars = check_sufficient_context(chunks)
        assert has_sufficient is False

    def test_multiple_chunks(self):
        """Test multiple chunks combined."""
        chunks = [
            {"score": 0.6, "chunk_text": "x" * 300},
            {"score": 0.5, "chunk_text": "x" * 300},
        ]
        has_sufficient, confidence, total_chars = check_sufficient_context(chunks)
        # Total chars = 600 >= 500, best distance = 0.5 < 0.7
        assert has_sufficient is True
        assert total_chars == 600


class TestPrepareSourceItems:
    """Tests for prepare_source_items function."""

    def test_empty_chunks(self):
        """Test empty chunks returns empty list."""
        result = prepare_source_items([])
        assert result == []

    def test_single_chunk(self):
        """Test single chunk source extraction."""
        chunks = [
            {
                "chunk_text": "This is a test chunk content",
                "score": 0.5,
                "metadata": {
                    "kap_report_id": 1,
                    "stock_symbol": "THYAO",
                    "report_title": "2024 Annual Report",
                    "published_at": "2024-01-15",
                    "filing_type": "FR",
                    "source_url": "https://kap.org.tr/1",
                }
            }
        ]
        sources = prepare_source_items(chunks)

        assert len(sources) == 1
        assert sources[0].kap_report_id == 1
        assert sources[0].stock_symbol == "THYAO"
        assert sources[0].filing_type == "FR"
        assert "This is a test chunk" in sources[0].chunk_preview

    def test_deduplication(self):
        """Test deduplication by kap_report_id."""
        chunks = [
            {
                "chunk_text": "Chunk 1",
                "metadata": {
                    "kap_report_id": 1,
                    "stock_symbol": "THYAO",
                    "report_title": "Report",
                    "filing_type": "FR",
                    "source_url": "url1",
                }
            },
            {
                "chunk_text": "Chunk 2",
                "metadata": {
                    "kap_report_id": 1,  # Same report
                    "stock_symbol": "THYAO",
                    "report_title": "Report",
                    "filing_type": "FR",
                    "source_url": "url1",
                }
            },
        ]
        sources = prepare_source_items(chunks)
        assert len(sources) == 1  # Deduplicated

    def test_different_reports(self):
        """Test chunks from different reports."""
        chunks = [
            {
                "chunk_text": "Chunk 1",
                "metadata": {
                    "kap_report_id": 1,
                    "stock_symbol": "THYAO",
                    "report_title": "Report 1",
                    "filing_type": "FR",
                    "source_url": "url1",
                }
            },
            {
                "chunk_text": "Chunk 2",
                "metadata": {
                    "kap_report_id": 2,  # Different report
                    "stock_symbol": "GARAN",
                    "report_title": "Report 2",
                    "filing_type": "FAR",
                    "source_url": "url2",
                }
            },
        ]
        sources = prepare_source_items(chunks)
        assert len(sources) == 2

    def test_chunk_without_kap_report_id(self):
        """Test chunk without kap_report_id is skipped."""
        chunks = [
            {
                "chunk_text": "Orphan chunk",
                "metadata": {
                    "stock_symbol": "THYAO",
                }
            }
        ]
        sources = prepare_source_items(chunks)
        assert len(sources) == 0

    def test_chunk_preview_truncation(self):
        """Test chunk preview is truncated to 100 chars."""
        long_text = "x" * 500
        chunks = [
            {
                "chunk_text": long_text,
                "metadata": {
                    "kap_report_id": 1,
                    "stock_symbol": "THYAO",
                    "report_title": "Report",
                    "filing_type": "FR",
                    "source_url": "url",
                }
            }
        ]
        sources = prepare_source_items(chunks)
        assert len(sources[0].chunk_preview) == 100


class TestChunkToDict:
    """Tests for _chunk_to_dict function."""

    def test_dict_input(self):
        """Test dict input returns same dict."""
        chunk_dict = {"chunk_text": "test", "score": 0.5, "metadata": {}}
        result = _chunk_to_dict(chunk_dict)
        assert result == chunk_dict

    def test_object_input(self):
        """Test object input conversion."""
        class MockChunk:
            chunk_text = "test content"
            score = 0.6
            metadata = {"key": "value"}

        result = _chunk_to_dict(MockChunk())
        assert result["chunk_text"] == "test content"
        assert result["score"] == 0.6
        assert result["metadata"]["key"] == "value"


class TestRunRetrieval:
    """Tests for run_retrieval function."""

    @pytest.mark.asyncio
    async def test_empty_result(self):
        """Test empty retrieval result."""
        with patch("app.services.agents.retrieval_agent.retrieve_chunks") as mock_retrieve:
            from app.services.rag.retriever import RetrievalResult
            mock_retrieve.return_value = RetrievalResult(
                query="test",
                stock_symbol=None,
                chunks=[],
                total_results=0,
            )

            result = await run_retrieval(
                query="test query",
                resolved_symbol=None,
                document_type=DocumentType.ANY,
            )

        assert result.has_sufficient_context is False
        assert len(result.chunks) == 0

    @pytest.mark.asyncio
    async def test_fr_filter(self):
        """Test FR document type filtering."""
        chunks_data = [
            {
                "chunk_text": "x" * 600,
                "score": 0.5,
                "metadata": {"filing_type": "FR", "kap_report_id": 1, "stock_symbol": "THYAO", "report_title": "R", "source_url": "u"}
            },
            {
                "chunk_text": "y" * 600,
                "score": 0.6,
                "metadata": {"filing_type": "FAR", "kap_report_id": 2, "stock_symbol": "THYAO", "report_title": "R", "source_url": "u"}
            },
        ]

        with patch("app.services.agents.retrieval_agent.retrieve_chunks") as mock_retrieve:
            from app.services.rag.retriever import RetrievalResult, RetrievedChunk
            # Create RetrievedChunk objects
            chunks = [
                RetrievedChunk(
                    chunk_text=c["chunk_text"],
                    score=c["score"],
                    metadata=c["metadata"]
                ) for c in chunks_data
            ]
            mock_retrieve.return_value = RetrievalResult(
                query="test",
                stock_symbol="THYAO",
                chunks=chunks,
                total_results=2,
            )

            result = await run_retrieval(
                query="test query",
                resolved_symbol="THYAO",
                document_type=DocumentType.FR,
            )

        # Only FR chunk should remain
        assert len(result.chunks) == 1
        assert result.chunks[0]["metadata"]["filing_type"] == "FR"

    @pytest.mark.asyncio
    async def test_far_filter(self):
        """Test FAR document type filtering."""
        chunks_data = [
            {
                "chunk_text": "x" * 600,
                "score": 0.5,
                "metadata": {"filing_type": "FR", "kap_report_id": 1, "stock_symbol": "THYAO", "report_title": "R", "source_url": "u"}
            },
            {
                "chunk_text": "y" * 600,
                "score": 0.6,
                "metadata": {"filing_type": "FAR", "kap_report_id": 2, "stock_symbol": "THYAO", "report_title": "R", "source_url": "u"}
            },
        ]

        with patch("app.services.agents.retrieval_agent.retrieve_chunks") as mock_retrieve:
            from app.services.rag.retriever import RetrievalResult, RetrievedChunk
            chunks = [
                RetrievedChunk(
                    chunk_text=c["chunk_text"],
                    score=c["score"],
                    metadata=c["metadata"]
                ) for c in chunks_data
            ]
            mock_retrieve.return_value = RetrievalResult(
                query="test",
                stock_symbol="THYAO",
                chunks=chunks,
                total_results=2,
            )

            result = await run_retrieval(
                query="test query",
                resolved_symbol="THYAO",
                document_type=DocumentType.FAR,
            )

        # Only FAR chunk should remain
        assert len(result.chunks) == 1
        assert result.chunks[0]["metadata"]["filing_type"] == "FAR"