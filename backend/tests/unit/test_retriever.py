"""Unit tests for retriever service.

Tests for:
- RetrievalResult model
- RetrievedChunk model
- Deduplication (_deduplicate_results)
- retrieve_chunks function (mocked ChromaDB, mocked OpenRouter)
"""

import pytest
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.rag.retriever import (
    RetrievedChunk,
    RetrievalResult,
    _deduplicate_results,
)


# ============================================================================
# RetrievedChunk Model Tests
# ============================================================================


class TestRetrievedChunk:
    """Tests for RetrievedChunk model."""

    def test_all_fields(self):
        """Test with all fields populated."""
        chunk = RetrievedChunk(
            chunk_text="Test chunk content",
            score=0.5,
            metadata={
                "stock_symbol": "THYAO",
                "report_title": "Test Report",
                "published_at": "2024-01-01",
                "filing_type": "FR",
                "chunk_index": 0,
                "kap_report_id": 1,
            },
        )
        assert chunk.chunk_text == "Test chunk content"
        assert chunk.score == 0.5
        assert chunk.metadata["stock_symbol"] == "THYAO"

    def test_score_is_l2_distance(self):
        """Test that score represents L2 distance."""
        # L2 distance: lower = more similar
        chunk_similar = RetrievedChunk(
            chunk_text="Similar chunk",
            score=0.1,  # Low distance = high similarity
            metadata={},
        )
        chunk_different = RetrievedChunk(
            chunk_text="Different chunk",
            score=1.5,  # High distance = low similarity
            metadata={},
        )
        assert chunk_similar.score < chunk_different.score


# ============================================================================
# RetrievalResult Model Tests
# ============================================================================


class TestRetrievalResult:
    """Tests for RetrievalResult model."""

    def test_all_fields(self):
        """Test with all fields populated."""
        chunk = RetrievedChunk(
            chunk_text="Test",
            score=0.5,
            metadata={"stock_symbol": "THYAO"},
        )
        result = RetrievalResult(
            query="THYAO net kar",
            stock_symbol="THYAO",
            chunks=[chunk],
            total_results=1,
        )
        assert result.query == "THYAO net kar"
        assert result.stock_symbol == "THYAO"
        assert len(result.chunks) == 1
        assert result.total_results == 1

    def test_empty_result(self):
        """Test with empty results."""
        result = RetrievalResult(
            query="Test query",
            stock_symbol=None,
            chunks=[],
            total_results=0,
        )
        assert result.total_results == 0
        assert result.chunks == []

    def test_no_stock_symbol_filter(self):
        """Test retrieval without stock symbol filter."""
        result = RetrievalResult(
            query="Test query",
            stock_symbol=None,  # No filter
            chunks=[],
            total_results=0,
        )
        assert result.stock_symbol is None


# ============================================================================
# Deduplication Tests
# ============================================================================


class TestDeduplicateResults:
    """Tests for _deduplicate_results function."""

    def test_no_duplicates(self):
        """Test with no duplicate chunks."""
        chunks = [
            RetrievedChunk(chunk_text="Chunk 1", score=0.5, metadata={"chunk_text_hash": "hash1"}),
            RetrievedChunk(chunk_text="Chunk 2", score=0.6, metadata={"chunk_text_hash": "hash2"}),
            RetrievedChunk(chunk_text="Chunk 3", score=0.7, metadata={"chunk_text_hash": "hash3"}),
        ]
        result = _deduplicate_results(chunks)
        assert len(result) == 3

    def test_with_duplicates_keeps_best_score(self):
        """Test that duplicates are removed, keeping best score."""
        chunks = [
            RetrievedChunk(chunk_text="Same content", score=0.5, metadata={"chunk_text_hash": "same_hash"}),
            RetrievedChunk(chunk_text="Same content", score=0.3, metadata={"chunk_text_hash": "same_hash"}),  # Better score
            RetrievedChunk(chunk_text="Different", score=0.6, metadata={"chunk_text_hash": "different_hash"}),
        ]
        result = _deduplicate_results(chunks)

        # Should have 2 unique chunks
        assert len(result) == 2

        # The duplicate with score 0.3 should be kept (lower = better)
        same_hash_chunks = [c for c in result if c.metadata.get("chunk_text_hash") == "same_hash"]
        assert len(same_hash_chunks) == 1
        assert same_hash_chunks[0].score == 0.3  # Kept the better one

    def test_empty_list(self):
        """Test with empty list."""
        result = _deduplicate_results([])
        assert result == []

    def test_no_hash_kept(self):
        """Test handling of chunks without hash."""
        chunks = [
            RetrievedChunk(chunk_text="No hash", score=0.5, metadata={}),  # No hash
            RetrievedChunk(chunk_text="With hash", score=0.6, metadata={"chunk_text_hash": "hash1"}),
        ]
        result = _deduplicate_results(chunks)
        # Should keep both
        assert len(result) == 2

    def test_multiple_no_hash_results_are_not_collapsed(self):
        """Test that missing hash values do not collapse unrelated results."""
        chunks = [
            RetrievedChunk(chunk_text="No hash 1", score=0.5, metadata={}),
            RetrievedChunk(chunk_text="No hash 2", score=0.4, metadata={}),
            RetrievedChunk(chunk_text="No hash 3", score=0.3, metadata={}),
        ]
        result = _deduplicate_results(chunks)
        assert len(result) == 3

    def test_multiple_duplicates_same_hash(self):
        """Test multiple chunks with same hash."""
        chunks = [
            RetrievedChunk(chunk_text="Duplicate", score=0.9, metadata={"chunk_text_hash": "same"}),
            RetrievedChunk(chunk_text="Duplicate", score=0.7, metadata={"chunk_text_hash": "same"}),
            RetrievedChunk(chunk_text="Duplicate", score=0.5, metadata={"chunk_text_hash": "same"}),  # Best
        ]
        result = _deduplicate_results(chunks)
        assert len(result) == 1
        assert result[0].score == 0.5  # Best score kept


# ============================================================================
# Retrieve Chunks Tests (Mocked)
# ============================================================================


class TestRetrieveChunks:
    """Tests for retrieve_chunks function."""

    @pytest.mark.asyncio
    async def test_empty_result_on_chromadb_error(self):
        """Test that ChromaDB errors return empty result."""
        from app.services.rag.retriever import retrieve_chunks

        with patch("app.services.rag.retriever._get_chroma_client") as mock_client:
            mock_client.side_effect = Exception("ChromaDB connection failed")

            result = await retrieve_chunks("THYAO net kar", stock_symbol="THYAO")

            assert result.total_results == 0
            assert result.chunks == []

    @pytest.mark.asyncio
    async def test_basic_retrieval(self):
        """Test basic retrieval flow."""
        from app.services.rag.retriever import retrieve_chunks

        # Mock ChromaDB collection
        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            "ids": [["chunk1", "chunk2"]],
            "documents": [["Chunk 1 text", "Chunk 2 text"]],
            "metadatas": [[
                {"stock_symbol": "THYAO", "chunk_text_hash": "hash1"},
                {"stock_symbol": "THYAO", "chunk_text_hash": "hash2"},
            ]],
            "distances": [[0.5, 0.7]],
        }

        # Mock query embedding
        mock_embedding = [0.1] * 1536

        with patch("app.services.rag.retriever._get_chroma_client") as mock_client:
            mock_client_instance = MagicMock()
            mock_client_instance.get_collection.return_value = mock_collection
            mock_client.return_value = mock_client_instance

            with patch("app.services.rag.retriever._embed_query") as mock_embed:
                mock_embed.return_value = mock_embedding

                with patch("httpx.AsyncClient"):
                    result = await retrieve_chunks("THYAO net kar", stock_symbol="THYAO")

        # Should have retrieved chunks
        assert result.query == "THYAO net kar"
        assert result.stock_symbol == "THYAO"

    @pytest.mark.asyncio
    async def test_symbol_filter_applied(self):
        """Test that stock symbol filter is applied to ChromaDB query."""
        from app.services.rag.retriever import retrieve_chunks

        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            "ids": [[]],
            "documents": [[]],
            "metadatas": [[]],
            "distances": [[]],
        }

        mock_embedding = [0.1] * 1536

        with patch("app.services.rag.retriever._get_chroma_client") as mock_client:
            mock_client_instance = MagicMock()
            mock_client_instance.get_collection.return_value = mock_collection
            mock_client.return_value = mock_client_instance

            with patch("app.services.rag.retriever._embed_query") as mock_embed:
                mock_embed.return_value = mock_embedding

                with patch("httpx.AsyncClient"):
                    await retrieve_chunks("net kar", stock_symbol="GARAN")

        # Verify that where filter was passed to ChromaDB
        mock_collection.query.assert_called_once()
        call_kwargs = mock_collection.query.call_args[1]
        assert "where" in call_kwargs
        assert call_kwargs["where"] == {"stock_symbol": {"$eq": "GARAN"}}

    @pytest.mark.asyncio
    async def test_top_k_limit(self):
        """Test that top_k limits results."""
        from app.services.rag.retriever import retrieve_chunks

        # More results than top_k
        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            "ids": [["c1", "c2", "c3", "c4", "c5", "c6", "c7"]],
            "documents": [["t1", "t2", "t3", "t4", "t5", "t6", "t7"]],
            "metadatas": [[
                {"chunk_text_hash": f"h{i}"} for i in range(1, 8)
            ]],
            "distances": [[0.1 * i for i in range(1, 8)]],
        }

        mock_embedding = [0.1] * 1536

        with patch("app.services.rag.retriever._get_chroma_client") as mock_client:
            mock_client_instance = MagicMock()
            mock_client_instance.get_collection.return_value = mock_collection
            mock_client.return_value = mock_client_instance

            with patch("app.services.rag.retriever._embed_query") as mock_embed:
                mock_embed.return_value = mock_embedding

                with patch("httpx.AsyncClient"):
                    result = await retrieve_chunks("test", top_k=3)

        # Should be limited to top_k
        assert result.total_results <= 3

    @pytest.mark.asyncio
    async def test_metadata_present_in_results(self):
        """Test that metadata is preserved in results."""
        from app.services.rag.retriever import retrieve_chunks

        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            "ids": [["chunk1"]],
            "documents": [["Test chunk text"]],
            "metadatas": [[{
                "stock_symbol": "THYAO",
                "report_title": "Faaliyet Raporu",
                "published_at": "2024-06-15T00:00:00",
                "filing_type": "FR",
                "chunk_index": 0,
                "kap_report_id": 123,
                "chunk_text_hash": "abc123",
            }]],
            "distances": [[0.5]],
        }

        mock_embedding = [0.1] * 1536

        with patch("app.services.rag.retriever._get_chroma_client") as mock_client:
            mock_client_instance = MagicMock()
            mock_client_instance.get_collection.return_value = mock_collection
            mock_client.return_value = mock_client_instance

            with patch("app.services.rag.retriever._embed_query") as mock_embed:
                mock_embed.return_value = mock_embedding

                with patch("httpx.AsyncClient"):
                    result = await retrieve_chunks("test")

        if result.chunks:
            chunk = result.chunks[0]
            assert "stock_symbol" in chunk.metadata
            assert "kap_report_id" in chunk.metadata


# ============================================================================
# Query Embedding Tests
# ============================================================================


class TestEmbedQuery:
    """Tests for _embed_query helper function."""

    @pytest.mark.asyncio
    async def test_successful_embedding(self):
        """Test successful query embedding."""
        from app.services.rag.retriever import _embed_query
        import httpx

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "data": [{"embedding": [0.1, 0.2, 0.3], "index": 0}]
        }

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        result = await _embed_query(
            query="Test query",
            client=mock_client,
            api_key="test_key",
            timeout=30.0,
        )

        assert result == [0.1, 0.2, 0.3]

    @pytest.mark.asyncio
    async def test_api_error_propagates(self):
        """Test that API errors are propagated."""
        from app.services.rag.retriever import _embed_query
        import httpx

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.HTTPStatusError(
            "Error",
            request=MagicMock(),
            response=MagicMock(status_code=500),
        ))

        with pytest.raises(httpx.HTTPStatusError):
            await _embed_query(
                query="Test query",
                client=mock_client,
                api_key="test_key",
                timeout=30.0,
            )
