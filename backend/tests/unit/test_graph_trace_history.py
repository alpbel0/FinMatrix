"""Unit tests for LangGraph trace history (Task 7.4/7.5)."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.chat import (
    ChartPayload,
    FinancialMetricSnapshot,
    NumericalAnalysisResult,
    QueryClassificationResult,
    RAGResponse,
    SourceItem,
    TextAnalysisResult,
)
from app.schemas.enums import DocumentType, QueryType
from app.services.data.provider_models import PeriodType
from app.services.agents.graph.nodes import (
    classify_query_node,
    merge_node,
    numerical_analysis_node,
    resolve_symbol_node,
    text_analysis_node,
)
from app.services.agents.graph.state import AgentState, NodeTraceEntry
from app.services.agents.graph.workflow import get_graph


# ============================================================================
# Fixtures
# ============================================================================


def make_classification(
    query_type: QueryType = QueryType.NUMERICAL_ANALYSIS,
    symbols: list[str] | None = None,
    needs_text_analysis: bool = True,
    needs_numerical_analysis: bool = True,
    needs_chart: bool = False,
) -> QueryClassificationResult:
    return QueryClassificationResult(
        query_type=query_type,
        symbols=symbols or ["THYAO"],
        needs_text_analysis=needs_text_analysis,
        needs_numerical_analysis=needs_numerical_analysis,
        needs_comparison=False,
        needs_chart=needs_chart,
        confidence=0.9,
    )


def make_numerical_result() -> NumericalAnalysisResult:
    return NumericalAnalysisResult(
        symbols=["THYAO"],
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
        key_points=["Net kar artışı var"],
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
    resolved_symbol: str | None = "THYAO",
    numerical_result: NumericalAnalysisResult | None = None,
    text_result: TextAnalysisResult | None = None,
    fallback_reason: str | None = None,
    node_history: list | None = None,
) -> AgentState:
    return AgentState(
        query="THYAO analiz et",
        user_id=1,
        session_id=42,
        classification=classification,
        resolved_symbol=resolved_symbol,
        numerical_result=numerical_result,
        text_result=text_result,
        response=None,
        fallback_reason=fallback_reason,
        node_history=node_history if node_history is not None else [],
    )


# ============================================================================
# node_history structure
# ============================================================================


class TestNodeHistoryStructure:
    """Tests for NodeTraceEntry structure in node_history."""

    @pytest.mark.asyncio
    async def test_classify_query_node_adds_entry(self):
        """classify_query_node adds one entry to node_history."""
        classification = make_classification(symbols=["THYAO"])
        with patch(
            "app.services.agents.graph.nodes.classify_query",
            new_callable=AsyncMock,
            return_value=classification,
        ):
            state = base_state(node_history=[])
            result = await classify_query_node(state)

        assert len(result["node_history"]) == 1
        entry = result["node_history"][0]
        assert entry["node"] == "classify_query"
        assert entry["status"] == "ok"
        assert entry["duration_ms"] >= 0
        assert entry["reason_code"] is None

    @pytest.mark.asyncio
    async def test_resolve_symbol_node_adds_entry(self):
        """resolve_symbol_node adds one entry to node_history."""
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

            state = base_state(classification=classification, node_history=[])
            result = await resolve_symbol_node(state)

        assert len(result["node_history"]) == 1
        entry = result["node_history"][0]
        assert entry["node"] == "resolve_symbol"
        assert entry["status"] == "ok"

    @pytest.mark.asyncio
    async def test_numerical_analysis_node_adds_entry(self):
        """numerical_analysis_node adds one entry to node_history."""
        numerical = make_numerical_result()
        with patch(
            "app.services.agents.graph.nodes.run_numerical_analysis",
            new_callable=AsyncMock,
            return_value=numerical,
        ), patch(
            "app.services.agents.graph.nodes.AsyncSessionLocal"
        ) as mock_session_cls:
            mock_session = AsyncMock()
            mock_session_cls.return_value.__aenter__.return_value = mock_session

            state = base_state(resolved_symbol="THYAO", node_history=[])
            result = await numerical_analysis_node(state)

        assert len(result["node_history"]) == 1
        entry = result["node_history"][0]
        assert entry["node"] == "numerical_analysis"
        assert entry["status"] == "ok"

    @pytest.mark.asyncio
    async def test_text_analysis_node_adds_entry(self):
        """text_analysis_node adds one entry to node_history."""
        text = make_text_result()
        with patch(
            "app.services.agents.text_analyst.run_text_analysis",
            new_callable=AsyncMock,
            return_value=text,
        ), patch(
            "app.services.agents.graph.nodes.AsyncSessionLocal"
        ) as mock_session_cls:
            mock_session = AsyncMock()
            mock_session_cls.return_value.__aenter__.return_value = mock_session

            state = base_state(node_history=[])
            result = await text_analysis_node(state)

        assert len(result["node_history"]) == 1
        entry = result["node_history"][0]
        assert entry["node"] == "text_analysis"
        assert entry["status"] == "ok"

    @pytest.mark.asyncio
    async def test_merge_node_adds_entry(self):
        """merge_node adds one entry to node_history."""
        rag = make_rag_response()
        with patch(
            "app.services.agents.graph.nodes.merge_analysis_results",
            return_value=rag,
        ):
            state = base_state(node_history=[])
            result = await merge_node(state)

        assert len(result["node_history"]) == 1
        entry = result["node_history"][0]
        assert entry["node"] == "merge"
        assert entry["status"] == "ok"

    @pytest.mark.asyncio
    async def test_all_node_entries_have_positive_duration(self):
        """All node entries have duration_ms >= 0."""
        classification = make_classification(symbols=["THYAO"])
        with patch(
            "app.services.agents.graph.nodes.classify_query",
            new_callable=AsyncMock,
            return_value=classification,
        ):
            state = base_state(node_history=[])
            result = await classify_query_node(state)

        entry = result["node_history"][0]
        assert isinstance(entry["duration_ms"], float)
        assert entry["duration_ms"] >= 0

    @pytest.mark.asyncio
    async def test_error_entry_has_reason_code(self):
        """Error entries have a non-None reason_code."""
        with patch(
            "app.services.agents.graph.nodes.classify_query",
            new_callable=AsyncMock,
            side_effect=RuntimeError("LLM unavailable"),
        ):
            state = base_state(node_history=[])
            result = await classify_query_node(state)

        entry = result["node_history"][0]
        assert entry["status"] == "error"
        assert entry["reason_code"] is not None

    @pytest.mark.asyncio
    async def test_skipped_entry_has_reason_code(self):
        """Skipped entries have a non-None reason_code."""
        state = base_state(classification=None, node_history=[])
        result = await resolve_symbol_node(state)

        entry = result["node_history"][0]
        assert entry["status"] == "skipped"
        assert entry["reason_code"] is not None


# ============================================================================
# Graph-level trace test
# ============================================================================


class TestGraphLevelTrace:
    """Test full graph invocation produces expected node_history entries."""

    @pytest.mark.asyncio
    async def test_graph_invoke_with_mocked_nodes(self):
        """Full graph invoke with all nodes mocked produces node_history with all traces."""
        classification = make_classification(
            symbols=["THYAO"],
            needs_numerical_analysis=True,
            needs_text_analysis=True,
        )
        numerical = make_numerical_result()
        text = make_text_result()
        rag = make_rag_response()

        # Track call order
        call_order = []

        async def mock_classify(query, http_client=None):
            call_order.append("classify_query")
            return classification

        async def mock_resolve_symbol(db, symbol):
            call_order.append("resolve_symbol")
            return "THYAO"

        async def mock_numerical(db, query, symbols, needs_chart, http_client):
            call_order.append("numerical_analysis")
            return numerical

        async def mock_text(
            *,
            db,
            user_id,
            session_id,
            query,
            resolved_symbols,
            classification,
            http_client,
        ):
            call_order.append("text_analysis")
            assert resolved_symbols == ["THYAO"]
            assert classification is not None
            return text

        def mock_merge(classification, resolved_symbols=None, resolved_symbol=None, numerical_result=None, text_result=None):
            call_order.append("merge")
            return rag

        with patch(
            "app.services.agents.graph.nodes.classify_query",
            side_effect=mock_classify,
        ), patch(
            "app.services.agents.graph.nodes.resolve_symbol",
            side_effect=mock_resolve_symbol,
        ), patch(
            "app.services.agents.graph.nodes.run_numerical_analysis",
            side_effect=mock_numerical,
        ), patch(
            "app.services.agents.text_analyst.run_text_analysis",
            side_effect=mock_text,
        ), patch(
            "app.services.agents.graph.nodes.merge_analysis_results",
            side_effect=mock_merge,
        ), patch(
            "app.services.agents.graph.nodes.AsyncSessionLocal"
        ) as mock_session_cls:
            mock_session = AsyncMock()
            mock_session_cls.return_value.__aenter__.return_value = mock_session

            graph = get_graph()
            initial_state: AgentState = {
                "query": "THYAO analiz et",
                "user_id": 1,
                "session_id": 42,
                "http_client": None,
                "classification": None,
                "resolved_symbols": None,
                "resolved_symbol": None,
                "text_result": None,
                "numerical_result": None,
                "response": None,
                "fallback_reason": None,
                "node_history": [],
            }

            result = await graph.ainvoke(initial_state)

        # Verify call order
        assert "classify_query" in call_order
        assert "resolve_symbol" in call_order
        assert "numerical_analysis" in call_order
        assert "text_analysis" in call_order
        assert "merge" in call_order

        # Verify node_history exists and has entries
        node_history = result.get("node_history", [])
        assert isinstance(node_history, list)
        assert len(node_history) >= 4  # at least classify, resolve, numerical, text, merge

        # All entries should have required fields
        for entry in node_history:
            assert "node" in entry
            assert "status" in entry
            assert "duration_ms" in entry
            assert "reason_code" in entry
            assert entry["status"] in ("ok", "error", "skipped")

    @pytest.mark.asyncio
    async def test_graph_singleton_returns_same_instance(self):
        """get_graph() called twice returns the same compiled graph instance."""
        graph1 = get_graph()
        graph2 = get_graph()
        assert graph1 is graph2
