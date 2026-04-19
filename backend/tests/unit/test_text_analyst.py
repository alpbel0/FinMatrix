"""Unit tests for CrewAI-ready text analyst wrapper."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.chat import (
    QueryUnderstandingResult,
    RAGResponse,
    RetrievalAgentResult,
    SourceItem,
)
from app.schemas.enums import DocumentType, QueryIntent
from app.services.agents.text_analyst import _extract_key_points, run_text_analysis
from app.services.chat_trace_service import ChatPipelineResult


class TestExtractKeyPoints:
    """Tests for answer key point extraction."""

    def test_extracts_non_empty_points(self):
        answer = """
        THYAO faaliyet raporunda denetim ve sürdürülebilirlik öne çıkıyor.
        - Bağımsız denetçi olumlu görüş bildirmiştir.
        - Rapor TSRS uyumlu sürdürülebilirlik raporu içerir.
        """
        points = _extract_key_points(answer)
        assert len(points) >= 2
        assert "olumlu görüş" in " ".join(points)

    def test_empty_answer(self):
        assert _extract_key_points("") == []


class TestRunTextAnalysis:
    """Tests for text analyst wrapper."""

    @pytest.mark.asyncio
    async def test_packages_pipeline_result(self):
        source = SourceItem(
            kap_report_id=211,
            stock_symbol="THYAO",
            report_title="Faaliyet Raporu",
            published_at=None,
            filing_type="FAR",
            source_url="https://kap.org/211",
            chunk_preview="Preview",
        )
        response = RAGResponse(
            answer_text="THYAO faaliyet raporunda denetim görüşü ve sürdürülebilirlik öne çıkıyor.",
            sources=[source],
            stock_symbol="THYAO",
            document_type=DocumentType.FAR,
            insufficient_context=False,
        )
        pipeline = ChatPipelineResult(
            response=response,
            understanding=QueryUnderstandingResult(
                normalized_query="THYAO faaliyet raporu",
                candidate_symbol="THYAO",
                document_type=DocumentType.FAR,
                intent=QueryIntent.SUMMARY,
                confidence=0.9,
            ),
            resolved_symbol="THYAO",
            retrieval=RetrievalAgentResult(
                chunks=[{"chunk_text": "Test", "score": 1.0, "metadata": {}}],
                sources=[source],
                has_sufficient_context=True,
                retrieval_confidence=0.72,
                context_total_chars=1000,
            ),
            memory_context="",
        )

        with patch("app.services.agents.text_analyst.run_document_pipeline", AsyncMock(return_value=pipeline)):
            result = await run_text_analysis(
                db=AsyncMock(),
                user_id=1,
                session_id=1,
                query="THYAO faaliyet raporu ne diyor?",
            )

        assert result.answer_text == response.answer_text
        assert result.stock_symbol == "THYAO"
        assert result.document_type == DocumentType.FAR
        assert result.insufficient_context is False
        assert result.retrieval_confidence == 0.72
        assert result.sources == [source]
        assert result.key_points

    @pytest.mark.asyncio
    async def test_insufficient_context_propagates(self):
        """Test that insufficient_context flag propagates from pipeline."""
        from app.schemas.chat import (
            QueryUnderstandingResult,
            RAGResponse,
            RetrievalAgentResult,
        )
        from app.schemas.enums import DocumentType, QueryIntent

        response = RAGResponse(
            answer_text="Yetersiz bilgi.",
            sources=[],
            stock_symbol=None,
            document_type=DocumentType.ANY,
            insufficient_context=True,
        )
        pipeline = ChatPipelineResult(
            response=response,
            understanding=QueryUnderstandingResult(
                normalized_query="test query",
                candidate_symbol=None,
                document_type=DocumentType.ANY,
                intent=QueryIntent.GENERIC,
                confidence=0.3,
            ),
            resolved_symbol=None,
            retrieval=RetrievalAgentResult(
                chunks=[],
                sources=[],
                has_sufficient_context=False,
                retrieval_confidence=0.0,
                context_total_chars=0,
            ),
            memory_context="",
        )

        with patch("app.services.agents.text_analyst.run_document_pipeline", AsyncMock(return_value=pipeline)):
            result = await run_text_analysis(
                db=AsyncMock(),
                user_id=1,
                session_id=1,
                query="test query",
            )

        assert result.insufficient_context is True
        assert result.retrieval_confidence == 0.0

    @pytest.mark.asyncio
    async def test_key_points_extraction_edge_cases(self):
        """Test key point extraction with edge cases."""
        from app.services.agents.text_analyst import _extract_key_points

        # Short lines should be filtered
        short_lines = "a\nbc\nvery long line here with more than 20 characters"
        points = _extract_key_points(short_lines)
        assert len(points) <= 2

        # Empty string
        assert _extract_key_points("") == []

        # Lines ending with colon should be filtered
        colon_lines = "Header:\n\nSome content here that is long enough"
        points = _extract_key_points(colon_lines)
        assert all("Header:" not in p for p in points)

    @pytest.mark.asyncio
    async def test_packages_pipeline_result_with_warnings(self):
        """Test that warning/confidence_note propagates."""
        from app.schemas.chat import (
            QueryUnderstandingResult,
            RAGResponse,
            RetrievalAgentResult,
        )
        from app.schemas.enums import DocumentType, QueryIntent

        response = RAGResponse(
            answer_text="Analiz tamamlandi.",
            sources=[],
            stock_symbol="THYAO",
            document_type=DocumentType.FR,
            insufficient_context=False,
            confidence_note="Bazi veriler eksik.",
        )
        pipeline = ChatPipelineResult(
            response=response,
            understanding=QueryUnderstandingResult(
                normalized_query="THYAO analiz",
                candidate_symbol="THYAO",
                document_type=DocumentType.FR,
                intent=QueryIntent.SUMMARY,
                confidence=0.8,
            ),
            resolved_symbol="THYAO",
            retrieval=RetrievalAgentResult(
                chunks=[{"chunk_text": "Test", "score": 1.0, "metadata": {}}],
                sources=[],
                has_sufficient_context=True,
                retrieval_confidence=0.7,
                context_total_chars=500,
            ),
            memory_context="",
        )

        with patch("app.services.agents.text_analyst.run_document_pipeline", AsyncMock(return_value=pipeline)):
            result = await run_text_analysis(
                db=AsyncMock(),
                user_id=1,
                session_id=1,
                query="THYAO analiz",
            )

        assert result.confidence_note == "Bazi veriler eksik."
        assert result.retrieval_confidence == 0.7

    @pytest.mark.asyncio
    async def test_source_metadata_preserved(self):
        """Test that source metadata is preserved through text analyst."""
        source = SourceItem(
            kap_report_id=211,
            stock_symbol="GARAN",
            report_title="GARAN Faaliyet Raporu",
            published_at=None,
            filing_type="FAR",
            source_url="https://kap.org/211",
            chunk_preview="Preview of GARAN analysis",
        )
        response = RAGResponse(
            answer_text="GARAN hakkinda analiz.",
            sources=[source],
            stock_symbol="GARAN",
            document_type=DocumentType.FAR,
            insufficient_context=False,
        )
        pipeline = ChatPipelineResult(
            response=response,
            understanding=QueryUnderstandingResult(
                normalized_query="GARAN raporu",
                candidate_symbol="GARAN",
                document_type=DocumentType.FAR,
                intent=QueryIntent.SUMMARY,
                confidence=0.85,
            ),
            resolved_symbol="GARAN",
            retrieval=RetrievalAgentResult(
                chunks=[],
                sources=[source],
                has_sufficient_context=True,
                retrieval_confidence=0.75,
                context_total_chars=800,
            ),
            memory_context="",
        )

        with patch("app.services.agents.text_analyst.run_document_pipeline", AsyncMock(return_value=pipeline)):
            result = await run_text_analysis(
                db=AsyncMock(),
                user_id=1,
                session_id=1,
                query="GARAN raporu",
            )

        assert len(result.sources) == 1
        assert result.sources[0].stock_symbol == "GARAN"
        assert result.sources[0].report_title == "GARAN Faaliyet Raporu"

    @pytest.mark.asyncio
    async def test_null_sources_handling(self):
        """Test handling of null/empty sources."""
        response = RAGResponse(
            answer_text="Sonuc bulunamadi.",
            sources=[],
            stock_symbol=None,
            document_type=DocumentType.ANY,
            insufficient_context=True,
        )
        pipeline = ChatPipelineResult(
            response=response,
            understanding=MagicMock(),
            resolved_symbol=None,
            retrieval=RetrievalAgentResult(
                chunks=[],
                sources=[],
                has_sufficient_context=False,
                retrieval_confidence=0.0,
                context_total_chars=0,
            ),
            memory_context="",
        )

        with patch("app.services.agents.text_analyst.run_document_pipeline", AsyncMock(return_value=pipeline)):
            result = await run_text_analysis(
                db=AsyncMock(),
                user_id=1,
                session_id=1,
                query="null test",
            )

        assert result.sources == []
        assert result.stock_symbol is None
