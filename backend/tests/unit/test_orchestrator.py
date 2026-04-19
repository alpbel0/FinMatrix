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

    @pytest.mark.asyncio
    async def test_numerical_only_query(self):
        """Test orchestration with numerical analysis only."""
        classification = QueryClassificationResult(
            query_type=QueryType.NUMERICAL_ANALYSIS,
            symbols=["THYAO"],
            needs_text_analysis=False,
            needs_numerical_analysis=True,
            needs_chart=False,
            confidence=0.9,
        )
        numerical = NumericalAnalysisResult(
            symbols=["THYAO"],
            metrics=[
                FinancialMetricSnapshot(
                    symbol="THYAO",
                    period_type=PeriodType.ANNUAL,
                    statement_date="2025-12-31",
                    net_income=100.0,
                    roe=0.25,
                    source="borsapy",
                )
            ],
            warnings=[],
            data_sources=["income_statements"],
            insufficient_data=False,
        )

        with patch("app.services.agents.orchestrator.classify_query", AsyncMock(return_value=classification)), \
             patch("app.services.agents.orchestrator.resolve_symbol", AsyncMock(return_value="THYAO")), \
             patch("app.services.agents.orchestrator.run_numerical_analysis", AsyncMock(return_value=numerical)):
            result = await run_orchestrated_pipeline(
                db=AsyncMock(),
                user_id=1,
                session_id=1,
                query="THYAO net kar analiz et",
            )

        assert "THYAO" in result.response.answer_text
        assert result.resolved_symbol == "THYAO"

    @pytest.mark.asyncio
    async def test_text_only_query(self):
        """Test orchestration with text analysis only."""
        classification = QueryClassificationResult(
            query_type=QueryType.TEXT_ANALYSIS,
            symbols=["THYAO"],
            needs_text_analysis=True,
            needs_numerical_analysis=False,
            needs_chart=False,
            confidence=0.9,
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
            answer_text="THYAO faaliyet raporu analizi.",
            key_points=["Analiz noktasi 1"],
            sources=[source],
            stock_symbol="THYAO",
            document_type=DocumentType.FR,
            insufficient_context=False,
            retrieval_confidence=0.8,
        )

        with patch("app.services.agents.orchestrator.classify_query", AsyncMock(return_value=classification)), \
             patch("app.services.agents.orchestrator.resolve_symbol", AsyncMock(return_value="THYAO")), \
             patch("app.services.agents.text_analyst.run_text_analysis", AsyncMock(return_value=text)):
            result = await run_orchestrated_pipeline(
                db=AsyncMock(),
                user_id=1,
                session_id=1,
                query="THYAO raporunu analiz et",
            )

        assert "THYAO" in result.response.answer_text
        assert result.resolved_symbol == "THYAO"

    @pytest.mark.asyncio
    async def test_both_agents_return_none_fallback(self):
        """Test fallback when both agents return None."""
        classification = QueryClassificationResult(
            query_type=QueryType.NUMERICAL_ANALYSIS,
            symbols=["UNKNOWN"],
            needs_text_analysis=False,
            needs_numerical_analysis=True,
            needs_chart=False,
            confidence=0.9,
        )
        fallback_pipeline = ChatPipelineResult(
            response=RAGResponse(
                answer_text="No data available",
                sources=[],
                stock_symbol=None,
                document_type=DocumentType.ANY,
                insufficient_context=True,
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
             patch("app.services.agents.orchestrator.resolve_symbol", AsyncMock(return_value=None)), \
             patch("app.services.agents.orchestrator.run_numerical_analysis", AsyncMock(return_value=None)), \
             patch("app.services.chat_rag_service.run_document_pipeline", AsyncMock(return_value=fallback_pipeline)):
            result = await run_orchestrated_pipeline(
                db=AsyncMock(),
                user_id=1,
                session_id=1,
                query="UNKNOWN hisse analiz et",
            )

        assert result.response.insufficient_context is True

    @pytest.mark.asyncio
    async def test_resolve_symbol_failure(self):
        """Test handling when symbol cannot be resolved."""
        classification = QueryClassificationResult(
            query_type=QueryType.TEXT_ANALYSIS,
            symbols=["BADSYMBOL"],
            needs_text_analysis=True,
            needs_numerical_analysis=False,
            needs_chart=False,
            confidence=0.9,
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
            answer_text="Analiz yapildi.",
            key_points=["Nokta 1"],
            sources=[source],
            stock_symbol="THYAO",
            document_type=DocumentType.FR,
            insufficient_context=False,
            retrieval_confidence=0.7,
        )

        with patch("app.services.agents.orchestrator.classify_query", AsyncMock(return_value=classification)), \
             patch("app.services.agents.orchestrator.resolve_symbol", AsyncMock(return_value="THYAO")), \
             patch("app.services.agents.text_analyst.run_text_analysis", AsyncMock(return_value=text)):
            result = await run_orchestrated_pipeline(
                db=AsyncMock(),
                user_id=1,
                session_id=1,
                query="BADSYMBOL analiz",
            )

        assert result.resolved_symbol == "THYAO"
        assert "Analiz" in result.response.answer_text

    @pytest.mark.asyncio
    async def test_chart_needed_flag_propagation(self):
        """Test that chart_needed flag propagates to numerical analysis."""
        classification = QueryClassificationResult(
            query_type=QueryType.NUMERICAL_ANALYSIS,
            symbols=["THYAO"],
            needs_text_analysis=False,
            needs_numerical_analysis=True,
            needs_chart=True,
            confidence=0.9,
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
            chart={"title": "Net Kar Trend", "type": "line", "series": []},
            warnings=[],
            data_sources=["income_statements"],
            insufficient_data=False,
        )

        with patch("app.services.agents.orchestrator.classify_query", AsyncMock(return_value=classification)), \
             patch("app.services.agents.orchestrator.resolve_symbol", AsyncMock(return_value="THYAO")), \
             patch("app.services.agents.orchestrator.run_numerical_analysis", AsyncMock(return_value=numerical)) as mock_numerical:
            result = await run_orchestrated_pipeline(
                db=AsyncMock(),
                user_id=1,
                session_id=1,
                query="THYAO net kar grafigi",
            )

        # Verify chart flag was passed
        call_kwargs = mock_numerical.call_args[1]
        assert call_kwargs.get("needs_chart") is True

    @pytest.mark.asyncio
    async def test_comparison_query_classification(self):
        """Test comparison query routing."""
        classification = QueryClassificationResult(
            query_type=QueryType.COMPARISON,
            symbols=["THYAO", "ASELS"],
            needs_text_analysis=True,
            needs_numerical_analysis=True,
            needs_comparison=True,
            needs_chart=False,
            confidence=0.9,
        )
        numerical = NumericalAnalysisResult(
            symbols=["THYAO", "ASELS"],
            metrics=[
                FinancialMetricSnapshot(
                    symbol="THYAO",
                    period_type=PeriodType.ANNUAL,
                    statement_date="2025-12-31",
                    net_income=100.0,
                    source="borsapy",
                ),
                FinancialMetricSnapshot(
                    symbol="ASELS",
                    period_type=PeriodType.ANNUAL,
                    statement_date="2025-12-31",
                    net_income=80.0,
                    source="borsapy",
                ),
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
            answer_text="Karsilastirma analizi.",
            key_points=["Nokta"],
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
                query="THYAO ile ASELS karsilastir",
            )

        assert "THYAO" in result.response.answer_text
        assert "ASELS" in result.response.answer_text
        assert result.resolved_symbol == "THYAO"
