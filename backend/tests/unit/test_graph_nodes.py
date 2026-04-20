"""Unit tests for LangGraph graph nodes (Task 7.3)."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.chat import (
    ChartPayload,
    FinancialMetricSnapshot,
    NumericalAnalysisResult,
    QueryClassificationResult,
    RAGResponse,
    TextAnalysisResult,
)
from app.schemas.enums import DocumentType, QueryType
from app.services.data.provider_models import PeriodType
from app.services.agents.graph.nodes import (
    classify_query_node,
    fallback_node,
    merge_node,
    numerical_analysis_node,
    resolve_symbol_node,
    text_analysis_node,
)
from app.services.agents.graph.state import AgentState
from app.services.chat_trace_service import ChatPipelineResult


# ============================================================================
# Fixtures
# ============================================================================


def make_classification(
    symbols: list[str] | None = None,
    query_type: QueryType = QueryType.NUMERICAL_ANALYSIS,
    needs_chart: bool = False,
    confidence: float = 0.9,
) -> QueryClassificationResult:
    return QueryClassificationResult(
        query_type=query_type,
        symbols=symbols or [],
        needs_text_analysis=False,
        needs_numerical_analysis=True,
        needs_comparison=False,
        needs_chart=needs_chart,
        confidence=confidence,
    )


def make_numerical_result(symbols: list[str] | None = None) -> NumericalAnalysisResult:
    return NumericalAnalysisResult(
        symbols=symbols or ["THYAO"],
        metrics=[
            FinancialMetricSnapshot(
                symbol="THYAO",
                period_type=PeriodType.ANNUAL,
                statement_date=date(2024, 12, 31),
                revenue=100_000_000.0,
                net_income=10_000_000.0,
                total_assets=500_000_000.0,
                total_equity=200_000_000.0,
                net_profit_growth=0.15,
            )
        ],
        comparison_table=None,
        chart=None,
        warnings=[],
        data_sources=["income_statements"],
        insufficient_data=False,
    )


def make_text_result() -> TextAnalysisResult:
    return TextAnalysisResult(
        answer_text="THYAO güçlü bir finansal performans sergiliyor.",
        key_points=["Net kar artışı var", "Borç/Özkaynak oranı iyileşti"],
        sources=[],
        stock_symbol="THYAO",
        document_type=DocumentType.FR,
        insufficient_context=False,
        confidence_note=None,
        retrieval_confidence=0.85,
    )


def make_rag_response() -> RAGResponse:
    return RAGResponse(
        answer_text="THYAO analiz sonucu.",
        sources=[],
        stock_symbol="THYAO",
        document_type=DocumentType.FR,
        confidence_note=None,
        insufficient_context=False,
        chart=None,
        comparison_table=None,
    )


def base_state(
    classification: QueryClassificationResult | None = None,
    resolved_symbol: str | None = None,
    numerical_result: NumericalAnalysisResult | None = None,
    text_result: TextAnalysisResult | None = None,
    fallback_reason: str | None = None,
    node_history: list | None = None,
) -> AgentState:
    return AgentState(
        query="THYAO analiz et",
        user_id=1,
        session_id=42,
        http_client=None,
        classification=classification,
        resolved_symbol=resolved_symbol,
        numerical_result=numerical_result,
        text_result=text_result,
        response=None,
        fallback_reason=fallback_reason,
        node_history=node_history if node_history is not None else [],
    )


# ============================================================================
# classify_query_node
# ============================================================================


class TestClassifyQueryNode:
    """Tests for classify_query_node."""

    @pytest.mark.asyncio
    async def test_ok(self):
        """classification is set when classify_query succeeds."""
        classification = make_classification(symbols=["THYAO"])
        with patch(
            "app.services.agents.graph.nodes.classify_query",
            new_callable=AsyncMock,
            return_value=classification,
        ) as mock_classify:
            state = base_state()
            result = await classify_query_node(state)

        assert result["classification"] is classification
        assert len(result["node_history"]) == 1
        assert result["node_history"][0]["node"] == "classify_query"
        assert result["node_history"][0]["status"] == "ok"
        assert result["node_history"][0]["reason_code"] is None
        mock_classify.assert_called_once_with("THYAO analiz et", http_client=None)

    @pytest.mark.asyncio
    async def test_error_sets_fallback_reason(self):
        """Exception sets classification=None and fallback_reason on error."""

        with patch(
            "app.services.agents.graph.nodes.classify_query",
            new_callable=AsyncMock,
            side_effect=RuntimeError("LLM unavailable"),
        ):
            state = base_state()
            result = await classify_query_node(state)

        assert result["classification"] is None
        assert result["fallback_reason"] == "classification_failed"
        assert len(result["node_history"]) == 1
        assert result["node_history"][0]["status"] == "error"
        assert result["node_history"][0]["reason_code"] == "classification_failed"


# ============================================================================
# resolve_symbol_node
# ============================================================================


class TestResolveSymbolNode:
    """Tests for resolve_symbol_node."""

    @pytest.mark.asyncio
    async def test_ok_resolved(self):
        """resolved_symbol is set when symbol is found in DB."""
        classification = make_classification(symbols=["THYAO"])
        with patch(
            "app.services.agents.graph.nodes.resolve_symbol",
            new_callable=AsyncMock,
            return_value="THYAO",
        ), patch(
            "app.services.agents.graph.nodes.AsyncSessionLocal"
        ) as mock_session_cls:
            mock_session = AsyncMock()
            mock_session_cls.return_value.__aenter__.return_value = mock_session

            state = base_state(classification=classification)
            result = await resolve_symbol_node(state)

        assert result["resolved_symbol"] == "THYAO"
        assert result["node_history"][0]["status"] == "ok"

    @pytest.mark.asyncio
    async def test_skipped_no_symbols_classification_none(self):
        """Skipped when classification is None."""
        state = base_state(classification=None)
        result = await resolve_symbol_node(state)

        assert result["resolved_symbol"] is None
        assert len(result["node_history"]) == 1
        assert result["node_history"][0]["status"] == "skipped"
        assert result["node_history"][0]["reason_code"] == "no_symbols"

    @pytest.mark.asyncio
    async def test_skipped_symbols_empty(self):
        """Skipped when classification.symbols is an empty list."""
        classification = make_classification(symbols=[])
        state = base_state(classification=classification)
        result = await resolve_symbol_node(state)

        assert result["resolved_symbol"] is None
        assert result["node_history"][0]["status"] == "skipped"
        assert result["node_history"][0]["reason_code"] == "no_symbols"

    @pytest.mark.asyncio
    async def test_skipped_symbol_not_found(self):
        """Skipped with reason symbol_not_found when resolve_symbol returns None."""
        classification = make_classification(symbols=["UNKNOWN"])
        with patch(
            "app.services.agents.graph.nodes.resolve_symbol",
            new_callable=AsyncMock,
            return_value=None,
        ), patch(
            "app.services.agents.graph.nodes.AsyncSessionLocal"
        ) as mock_session_cls:
            mock_session = AsyncMock()
            mock_session_cls.return_value.__aenter__.return_value = mock_session

            state = base_state(classification=classification)
            result = await resolve_symbol_node(state)

        assert result["resolved_symbol"] is None
        assert result["node_history"][0]["status"] == "skipped"
        assert result["node_history"][0]["reason_code"] == "symbol_not_found"

    @pytest.mark.asyncio
    async def test_error_sets_fallback_reason(self):
        """Exception sets fallback_reason=symbol_resolve_error."""
        classification = make_classification(symbols=["THYAO"])
        with patch(
            "app.services.agents.graph.nodes.resolve_symbol",
            new_callable=AsyncMock,
            side_effect=RuntimeError("DB connection failed"),
        ), patch(
            "app.services.agents.graph.nodes.AsyncSessionLocal"
        ) as mock_session_cls:
            mock_session = AsyncMock()
            mock_session_cls.return_value.__aenter__.return_value = mock_session

            state = base_state(classification=classification)
            result = await resolve_symbol_node(state)

        assert result["resolved_symbol"] is None
        assert result["fallback_reason"] == "symbol_resolve_error"
        assert result["node_history"][0]["status"] == "error"
        assert result["node_history"][0]["reason_code"] == "symbol_resolve_error"


# ============================================================================
# numerical_analysis_node
# ============================================================================


class TestNumericalAnalysisNode:
    """Tests for numerical_analysis_node."""

    @pytest.mark.asyncio
    async def test_ok(self):
        """numerical_result is set when resolved_symbol is present."""
        classification = make_classification(symbols=["THYAO"], needs_chart=True)
        numerical = make_numerical_result(symbols=["THYAO"])

        with patch(
            "app.services.agents.graph.nodes.run_numerical_analysis",
            new_callable=AsyncMock,
            return_value=numerical,
        ), patch(
            "app.services.agents.graph.nodes.AsyncSessionLocal"
        ) as mock_session_cls:
            mock_session = AsyncMock()
            mock_session_cls.return_value.__aenter__.return_value = mock_session

            state = base_state(
                classification=classification,
                resolved_symbol="THYAO",
            )
            result = await numerical_analysis_node(state)

        assert result["numerical_result"] is numerical
        assert result["node_history"][0]["status"] == "ok"

    @pytest.mark.asyncio
    async def test_skipped_no_symbol(self):
        """Skipped when resolved_symbol is None."""
        state = base_state(resolved_symbol=None)
        result = await numerical_analysis_node(state)

        assert result["numerical_result"] is None
        assert result["node_history"][0]["status"] == "skipped"
        assert result["node_history"][0]["reason_code"] == "no_symbol"

    @pytest.mark.asyncio
    async def test_error(self):
        """Exception sets numerical_result=None with error status."""
        with patch(
            "app.services.agents.graph.nodes.run_numerical_analysis",
            new_callable=AsyncMock,
            side_effect=RuntimeError("DB query failed"),
        ), patch(
            "app.services.agents.graph.nodes.AsyncSessionLocal"
        ) as mock_session_cls:
            mock_session = AsyncMock()
            mock_session_cls.return_value.__aenter__.return_value = mock_session

            state = base_state(resolved_symbol="THYAO")
            result = await numerical_analysis_node(state)

        assert result["numerical_result"] is None
        assert result["node_history"][0]["status"] == "error"
        assert result["node_history"][0]["reason_code"] == "numerical_failed"


# ============================================================================
# text_analysis_node
# ============================================================================


class TestTextAnalysisNode:
    """Tests for text_analysis_node."""

    @pytest.mark.asyncio
    async def test_ok(self):
        """text_result is set when run_text_analysis succeeds."""
        text_result = make_text_result()
        with patch(
            "app.services.agents.text_analyst.run_text_analysis",
            new_callable=AsyncMock,
            return_value=text_result,
        ), patch(
            "app.services.agents.graph.nodes.AsyncSessionLocal"
        ) as mock_session_cls:
            mock_session = AsyncMock()
            mock_session_cls.return_value.__aenter__.return_value = mock_session

            state = base_state()
            result = await text_analysis_node(state)

        assert result["text_result"] is text_result
        assert result["node_history"][0]["status"] == "ok"

    @pytest.mark.asyncio
    async def test_error(self):
        """Exception sets text_result=None with error status."""
        with patch(
            "app.services.agents.text_analyst.run_text_analysis",
            new_callable=AsyncMock,
            side_effect=RuntimeError("RAG retrieval failed"),
        ), patch(
            "app.services.agents.graph.nodes.AsyncSessionLocal"
        ) as mock_session_cls:
            mock_session = AsyncMock()
            mock_session_cls.return_value.__aenter__.return_value = mock_session

            state = base_state()
            result = await text_analysis_node(state)

        assert result["text_result"] is None
        assert result["node_history"][0]["status"] == "error"
        assert result["node_history"][0]["reason_code"] == "text_analysis_failed"


# ============================================================================
# merge_node
# ============================================================================


class TestMergeNode:
    """Tests for merge_node."""

    @pytest.mark.asyncio
    async def test_ok(self):
        """response is set when merge_analysis_results succeeds."""
        classification = make_classification(symbols=["THYAO"])
        numerical = make_numerical_result(symbols=["THYAO"])
        text = make_text_result()
        rag = make_rag_response()

        with patch(
            "app.services.agents.graph.nodes.merge_analysis_results",
            return_value=rag,
        ):
            state = base_state(
                classification=classification,
                resolved_symbol="THYAO",
                numerical_result=numerical,
                text_result=text,
            )
            result = await merge_node(state)

        assert result["response"] is rag
        assert result["node_history"][0]["status"] == "ok"

    @pytest.mark.asyncio
    async def test_error(self):
        """Exception sets response=None with error status."""
        with patch(
            "app.services.agents.graph.nodes.merge_analysis_results",
            side_effect=RuntimeError("Merge configuration error"),
        ):
            state = base_state()
            result = await merge_node(state)

        assert result["response"] is None
        assert result["node_history"][0]["status"] == "error"
        assert result["node_history"][0]["reason_code"] == "merge_failed"


# ============================================================================
# fallback_node
# ============================================================================


class TestFallbackNode:
    """Tests for fallback_node."""

    @pytest.mark.asyncio
    async def test_ok_uses_pipeline_response(self):
        """response is taken from pipeline_result.response on success."""
        rag = make_rag_response()
        pipeline_result = ChatPipelineResult(
            response=rag,
            understanding=MagicMock(),
            resolved_symbol="THYAO",
            retrieval=MagicMock(),
            memory_context="",
        )
        with patch(
            "app.services.chat_rag_service.run_document_pipeline",
            new_callable=AsyncMock,
            return_value=pipeline_result,
        ), patch(
            "app.services.agents.graph.nodes.AsyncSessionLocal"
        ) as mock_session_cls:
            mock_session = AsyncMock()
            mock_session_cls.return_value.__aenter__.return_value = mock_session

            state = base_state(fallback_reason="classification_failed")
            result = await fallback_node(state)

        assert result["response"] is rag
        entry = result["node_history"][0]
        assert entry["status"] == "ok"
        assert entry["reason_code"] == "classification_failed"

    @pytest.mark.asyncio
    async def test_error(self):
        """Exception sets response=None with error status."""
        with patch(
            "app.services.chat_rag_service.run_document_pipeline",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Pipeline unavailable"),
        ), patch(
            "app.services.agents.graph.nodes.AsyncSessionLocal"
        ) as mock_session_cls:
            mock_session = AsyncMock()
            mock_session_cls.return_value.__aenter__.return_value = mock_session

            state = base_state(fallback_reason="classification_failed")
            result = await fallback_node(state)

        assert result["response"] is None
        assert result["node_history"][0]["status"] == "error"
        assert result["node_history"][0]["reason_code"] == "fallback_failed"


# ============================================================================
# NodeTraceEntry structure
# ============================================================================


class TestNodeTraceEntryStructure:
    """Verify NodeTraceEntry contents and duration_ms correctness."""

    @pytest.mark.asyncio
    async def test_duration_ms_is_positive_float(self):
        """duration_ms is a positive number (time elapsed)."""
        import time

        classification = make_classification(symbols=["THYAO"])
        with patch(
            "app.services.agents.graph.nodes.classify_query",
            new_callable=AsyncMock,
            return_value=classification,
        ):
            state = base_state()
            result = await classify_query_node(state)

        entry = result["node_history"][0]
        assert "duration_ms" in entry
        assert isinstance(entry["duration_ms"], float)
        assert entry["duration_ms"] >= 0

    @pytest.mark.asyncio
    async def test_node_history_append_behavior(self):
        """node_history returns a list with a single entry (append behavior)."""
        classification = make_classification(symbols=["THYAO"])
        with patch(
            "app.services.agents.graph.nodes.classify_query",
            new_callable=AsyncMock,
            return_value=classification,
        ):
            state = base_state(node_history=[])
            result = await classify_query_node(state)

        assert isinstance(result["node_history"], list)
        assert len(result["node_history"]) == 1
        assert result["node_history"][0]["node"] == "classify_query"
