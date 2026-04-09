"""Unit tests for response agent.

Tests:
- GENERIC intent handling (greeting)
- Insufficient context handling
- Response generation
- Error handling
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.schemas.enums import DocumentType, QueryIntent
from app.schemas.chat import QueryUnderstandingResult, RetrievalAgentResult, RAGResponse
from app.services.agents.response_agent import (
    GREETING_RESPONSE,
    INSUFFICIENT_CONTEXT_RESPONSE,
    _format_context_chunks,
    generate_response,
)


class TestFormatContextChunks:
    """Tests for _format_context_chunks function."""

    def test_empty_chunks(self):
        """Test empty chunks returns no source message."""
        result = _format_context_chunks([])
        assert result == "KAYNAK BULUNAMADI"

    def test_single_chunk(self):
        """Test single chunk formatting."""
        chunks = [
            {
                "chunk_text": "Test content",
                "metadata": {
                    "stock_symbol": "THYAO",
                    "report_title": "2024 Annual",
                    "filing_type": "FR",
                }
            }
        ]
        result = _format_context_chunks(chunks)
        assert "[Kaynak 1]" in result
        assert "THYAO" in result
        assert "2024 Annual" in result

    def test_chunk_truncation(self):
        """Test long chunk is truncated."""
        chunks = [
            {
                "chunk_text": "x" * 1000,
                "metadata": {
                    "stock_symbol": "THYAO",
                    "report_title": "Report",
                    "filing_type": "FR",
                }
            }
        ]
        result = _format_context_chunks(chunks)
        assert "..." in result

    def test_multiple_chunks(self):
        """Test multiple chunks formatting."""
        chunks = [
            {
                "chunk_text": "Content 1",
                "metadata": {
                    "stock_symbol": "THYAO",
                    "report_title": "Report 1",
                    "filing_type": "FR",
                }
            },
            {
                "chunk_text": "Content 2",
                "metadata": {
                    "stock_symbol": "GARAN",
                    "report_title": "Report 2",
                    "filing_type": "FAR",
                }
            },
        ]
        result = _format_context_chunks(chunks)
        assert "[Kaynak 1]" in result
        assert "[Kaynak 2]" in result


class TestGenerateResponse:
    """Tests for generate_response function."""

    @pytest.mark.asyncio
    async def test_generic_intent_greeting(self):
        """Test GENERIC intent returns greeting response."""
        understanding = QueryUnderstandingResult(
            normalized_query="merhaba",
            candidate_symbol=None,
            document_type=DocumentType.ANY,
            intent=QueryIntent.GENERIC,
            confidence=1.0,
        )
        retrieval = RetrievalAgentResult(
            chunks=[],
            sources=[],
            has_sufficient_context=False,
            retrieval_confidence=0.0,
            context_total_chars=0,
        )

        result = await generate_response(
            original_query="merhaba",
            understanding=understanding,
            retrieval=retrieval,
        )

        assert result.answer_text == GREETING_RESPONSE
        assert result.insufficient_context is False
        assert "Sistem belge odaklı" in result.confidence_note

    @pytest.mark.asyncio
    async def test_insufficient_context(self):
        """Test insufficient context returns fallback response."""
        understanding = QueryUnderstandingResult(
            normalized_query="thyao rapor",
            candidate_symbol="THYAO",
            document_type=DocumentType.FR,
            intent=QueryIntent.SUMMARY,
            confidence=0.8,
        )
        retrieval = RetrievalAgentResult(
            chunks=[],
            sources=[],
            has_sufficient_context=False,
            retrieval_confidence=0.3,
            context_total_chars=0,
        )

        result = await generate_response(
            original_query="thyao rapor",
            understanding=understanding,
            retrieval=retrieval,
        )

        assert result.answer_text == INSUFFICIENT_CONTEXT_RESPONSE
        assert result.insufficient_context is True

    @pytest.mark.asyncio
    async def test_successful_response(self):
        """Test successful response generation."""
        understanding = QueryUnderstandingResult(
            normalized_query="thyao yıllık rapor",
            candidate_symbol="THYAO",
            document_type=DocumentType.FR,
            intent=QueryIntent.SUMMARY,
            confidence=0.9,
        )
        retrieval = RetrievalAgentResult(
            chunks=[
                {
                    "chunk_text": "THYAO 2024 net karı 163 milyar TL olarak gerçekleşmiştir.",
                    "score": 0.5,
                    "metadata": {
                        "kap_report_id": 1,
                        "stock_symbol": "THYAO",
                        "report_title": "2024 Annual Report",
                        "filing_type": "FR",
                        "source_url": "https://kap.org.tr/1",
                    }
                }
            ],
            sources=[],
            has_sufficient_context=True,
            retrieval_confidence=0.8,
            context_total_chars=100,
        )

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": "THYAO'nun 2024 yıllık raporuna göre net karı 163 milyar TL'dir. (Kaynak: KAP FR 2024)"
                }
            }]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        with patch("app.services.agents.response_agent.load_prompt") as mock_load:
            mock_load.return_value = MagicMock(
                model="test-model",
                system_prompt="test",
                user_prompt_template="{original_query}",
                temperature=0.7,
                max_tokens=2048,
                format_user_prompt=lambda **kw: "test prompt"
            )

            result = await generate_response(
                original_query="thyao yıllık rapor",
                understanding=understanding,
                retrieval=retrieval,
                http_client=mock_client,
            )

        assert "163 milyar" in result.answer_text
        assert result.insufficient_context is False

    @pytest.mark.asyncio
    async def test_memory_context_is_passed_to_prompt(self):
        """Test recent chat context is included in prompt formatting."""
        understanding = QueryUnderstandingResult(
            normalized_query="thyao rapor",
            candidate_symbol="THYAO",
            document_type=DocumentType.FR,
            intent=QueryIntent.SUMMARY,
            confidence=0.9,
        )
        retrieval = RetrievalAgentResult(
            chunks=[{"chunk_text": "x" * 600, "score": 0.4, "metadata": {"kap_report_id": 1, "stock_symbol": "THYAO", "report_title": "R", "filing_type": "FR", "source_url": "u"}}],
            sources=[],
            has_sufficient_context=True,
            retrieval_confidence=0.8,
            context_total_chars=600,
        )

        mock_response = MagicMock()
        mock_response.json.return_value = {"choices": [{"message": {"content": "Test response"}}]}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        captured_kwargs: dict = {}

        def _format_prompt(**kwargs):
            captured_kwargs.update(kwargs)
            return "test prompt"

        with patch("app.services.agents.response_agent.load_prompt") as mock_load:
            mock_load.return_value = MagicMock(
                model="test-model",
                system_prompt="test",
                user_prompt_template="{original_query}",
                temperature=0.7,
                max_tokens=2048,
                format_user_prompt=_format_prompt,
            )

            await generate_response(
                original_query="thyao rapor",
                understanding=understanding,
                retrieval=retrieval,
                memory_context="Kullanıcı: Önceki soru",
                http_client=mock_client,
            )

        assert captured_kwargs["memory_context"] == "Kullanıcı: Önceki soru"

    @pytest.mark.asyncio
    async def test_low_confidence_note(self):
        """Test low confidence adds note."""
        understanding = QueryUnderstandingResult(
            normalized_query="thyao rapor",
            candidate_symbol="THYAO",
            document_type=DocumentType.FR,
            intent=QueryIntent.SUMMARY,
            confidence=0.9,
        )
        retrieval = RetrievalAgentResult(
            chunks=[{"chunk_text": "x" * 600, "score": 0.5, "metadata": {"kap_report_id": 1, "stock_symbol": "THYAO", "report_title": "R", "filing_type": "FR", "source_url": "u"}}],
            sources=[],
            has_sufficient_context=True,
            retrieval_confidence=0.3,  # Low confidence
            context_total_chars=600,
        )

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Test response"}}]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        with patch("app.services.agents.response_agent.load_prompt") as mock_load:
            mock_load.return_value = MagicMock(
                model="test-model",
                system_prompt="test",
                user_prompt_template="{original_query}",
                temperature=0.7,
                max_tokens=2048,
                format_user_prompt=lambda **kw: "test prompt"
            )

            result = await generate_response(
                original_query="thyao rapor",
                understanding=understanding,
                retrieval=retrieval,
                http_client=mock_client,
            )

        assert result.confidence_note is not None
        assert "düşük güven" in result.confidence_note.lower()

    @pytest.mark.asyncio
    async def test_api_error(self):
        """Test API error returns error response."""
        understanding = QueryUnderstandingResult(
            normalized_query="thyao rapor",
            candidate_symbol="THYAO",
            document_type=DocumentType.FR,
            intent=QueryIntent.SUMMARY,
            confidence=0.9,
        )
        retrieval = RetrievalAgentResult(
            chunks=[{"chunk_text": "x" * 600, "score": 0.5, "metadata": {"kap_report_id": 1, "stock_symbol": "THYAO", "report_title": "R", "filing_type": "FR", "source_url": "u"}}],
            sources=[],
            has_sufficient_context=True,
            retrieval_confidence=0.8,
            context_total_chars=600,
        )

        mock_client = AsyncMock()
        mock_client.post.side_effect = Exception("API error")

        with patch("app.services.agents.response_agent.load_prompt") as mock_load:
            mock_load.return_value = MagicMock(
                model="test-model",
                system_prompt="test",
                user_prompt_template="{original_query}",
                temperature=0.7,
                max_tokens=2048,
                format_user_prompt=lambda **kw: "test prompt"
            )

            result = await generate_response(
                original_query="thyao rapor",
                understanding=understanding,
                retrieval=retrieval,
                http_client=mock_client,
            )

        assert "hata" in result.answer_text.lower()
        assert result.insufficient_context is True
