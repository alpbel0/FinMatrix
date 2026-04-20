"""Unit tests for LangGraph fallback routing (Task 7.4/7.5)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.chat import (
    QueryClassificationResult,
    RAGResponse,
    SourceItem,
)
from app.schemas.enums import DocumentType, QueryType
from app.services.agents.graph.nodes import fallback_node
from app.services.agents.graph.state import AgentState
from app.services.agents.graph.workflow import _route_after_symbol


# ============================================================================
# Fixtures
# ============================================================================


def make_classification(
    query_type: QueryType = QueryType.NUMERICAL_ANALYSIS,
    symbols: list[str] | None = None,
    needs_text_analysis: bool = False,
    needs_numerical_analysis: bool = True,
) -> QueryClassificationResult:
    return QueryClassificationResult(
        query_type=query_type,
        symbols=symbols or ["THYAO"],
        needs_text_analysis=needs_text_analysis,
        needs_numerical_analysis=needs_numerical_analysis,
        needs_comparison=False,
        needs_chart=False,
        confidence=0.9,
    )


def base_state(
    classification: QueryClassificationResult | None = None,
    fallback_reason: str | None = None,
    node_history: list | None = None,
) -> AgentState:
    return AgentState(
        query="THYAO analiz et",
        user_id=1,
        session_id=42,
        classification=classification,
        fallback_reason=fallback_reason,
        node_history=node_history if node_history is not None else [],
    )


# ============================================================================
# _route_after_symbol fallback conditions
# ============================================================================


class TestFallbackRouting:
    """Tests for fallback routing conditions."""

    def test_classification_none_routes_to_fallback(self):
        """classification=None routes to 'fallback'."""
        state = base_state(classification=None)
        assert _route_after_symbol(state) == "fallback"

    def test_fallback_reason_set_routes_to_fallback(self):
        """Any fallback_reason set routes to 'fallback'."""
        classification = make_classification()
        state = base_state(
            classification=classification,
            fallback_reason="classification_failed",
        )
        assert _route_after_symbol(state) == "fallback"

    def test_general_query_type_routes_to_fallback(self):
        """QueryType.GENERAL always routes to 'fallback'."""
        classification = make_classification(query_type=QueryType.GENERAL)
        state = base_state(classification=classification)
        assert _route_after_symbol(state) == "fallback"

    def test_text_analysis_type_not_general_routes_out(self):
        """QueryType.TEXT_ANALYSIS (not GENERAL) does NOT route to fallback."""
        classification = make_classification(
            query_type=QueryType.TEXT_ANALYSIS,
            needs_numerical_analysis=False,
            needs_text_analysis=True,
        )
        state = base_state(classification=classification)
        assert _route_after_symbol(state) == "text_analysis"


# ============================================================================
# fallback_node
# ============================================================================


class TestFallbackNode:
    """Tests for fallback_node."""

    @pytest.mark.asyncio
    async def test_ok_uses_pipeline_response(self):
        """fallback_node returns pipeline_result.response on success."""
        rag = RAGResponse(
            answer_text="Belge bazlı yanıt.",
            sources=[],
            stock_symbol="THYAO",
            document_type=DocumentType.ANY,
            confidence_note=None,
            insufficient_context=False,
            chart=None,
            comparison_table=None,
        )
        pipeline_result = MagicMock()
        pipeline_result.response = rag

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
    async def test_error_sets_fallback_failed(self):
        """Exception in fallback_node sets response=None with error status."""
        with patch(
            "app.services.chat_rag_service.run_document_pipeline",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Pipeline unavailable"),
        ), patch(
            "app.services.agents.graph.nodes.AsyncSessionLocal"
        ) as mock_session_cls:
            mock_session = AsyncMock()
            mock_session_cls.return_value.__aenter__.return_value = mock_session

            state = base_state(fallback_reason="symbol_resolve_error")
            result = await fallback_node(state)

        assert result["response"] is None
        entry = result["node_history"][0]
        assert entry["status"] == "error"
        assert entry["reason_code"] == "fallback_failed"

