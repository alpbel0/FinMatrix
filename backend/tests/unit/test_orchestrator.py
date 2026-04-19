"""Unit tests for orchestrator routing and merger integration."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.chat import (
    FinancialMetricSnapshot,
    NumericalAnalysisResult,
    QueryClassificationResult,
    RetrievalAgentResult,
    RAGResponse,
    SourceItem,
    TextAnalysisResult,
)
from app.schemas.enums import DocumentType, QueryType
from app.services.agents.orchestrator import run_orchestrated_pipeline
from app.services.chat_trace_service import ChatPipelineResult
from app.services.data.provider_models import PeriodType


class TestRunOrchestratedPipeline:
    @pytest.mark.asyncio
    async def test_general_query_falls_back_to_document_pipeline(self):
        classification = QueryClassificationResult(
            query_type=QueryType.GENERAL,
            symbols=[],
            confidence=0.9,
        )
        fallback_pipeline = ChatPipelineResult(
            response=RAGResponse(
                answer_text="Fallback",
                sources=[],
                stock_symbol=None,
                document_type=DocumentType.ANY,
                insufficient_context=False,
            ),
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

        with patch("app.services.agents.orchestrator.classify_query", AsyncMock(return_value=classification)), \
             patch("app.services.chat_rag_service.run_document_pipeline", AsyncMock(return_value=fallback_pipeline)):
            result = await run_orchestrated_pipeline(
                db=AsyncMock(),
                user_id=1,
                session_id=1,
                query="merhaba",
            )

        assert result.response.answer_text == "Fallback"

    @pytest.mark.asyncio
    async def test_combined_query_runs_both_agents_and_merges(self):
        classification = QueryClassificationResult(
            query_type=QueryType.COMPARISON,
            symbols=["THYAO"],
            needs_text_analysis=True,
            needs_numerical_analysis=True,
            needs_comparison=True,
            needs_chart=False,
            confidence=0.8,
        )
        numerical = NumericalAnalysisResult(
            symbols=["THYAO"],
            metrics=[
                FinancialMetricSnapshot(
                    symbol="THYAO",
                    period_type=PeriodType.ANNUAL,
                    statement_date="2025-12-31",
                    net_income=100.0,
                    source="borsapy",
                )
            ],
            warnings=[],
            data_sources=["income_statements"],
            insufficient_data=False,
        )
        source = SourceItem(
            kap_report_id=1,
            stock_symbol="THYAO",
            report_title="Report",
            published_at=None,
            filing_type="FR",
            source_url="https://kap/1",
            chunk_preview="Preview",
        )
        text = TextAnalysisResult(
            answer_text="Text block",
            key_points=["Point"],
            sources=[source],
            stock_symbol="THYAO",
            document_type=DocumentType.FR,
            insufficient_context=False,
            retrieval_confidence=0.75,
        )

        with patch("app.services.agents.orchestrator.classify_query", AsyncMock(return_value=classification)), \
             patch("app.services.agents.orchestrator.resolve_symbol", AsyncMock(return_value="THYAO")), \
             patch("app.services.agents.orchestrator.run_numerical_analysis", AsyncMock(return_value=numerical)), \
             patch("app.services.agents.text_analyst.run_text_analysis", AsyncMock(return_value=text)):
            result = await run_orchestrated_pipeline(
                db=AsyncMock(),
                user_id=1,
                session_id=1,
                query="THYAO net karini analiz et ve riskini degerlendir",
            )

        assert "Text block" in result.response.answer_text
        assert result.response.sources == [source]
        assert result.resolved_symbol == "THYAO"
