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

        with patch("app.services.agents.text_analyst.run_chat_pipeline", AsyncMock(return_value=pipeline)):
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
