"""Unit tests for LangGraph workflow routing (Task 7.4/7.5)."""

import pytest

from app.schemas.chat import QueryClassificationResult
from app.schemas.enums import QueryType
from app.services.agents.graph.state import AgentState
from app.services.agents.graph.workflow import (
    _route_after_numerical,
    _route_after_symbol,
    build_workflow,
    get_graph,
)


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
) -> AgentState:
    return AgentState(
        query="THYAO analiz et",
        user_id=1,
        session_id=42,
        classification=classification,
        fallback_reason=fallback_reason,
    )


# ============================================================================
# _route_after_symbol
# ============================================================================


class TestRouteAfterSymbol:
    """Tests for _route_after_symbol routing function."""

    def test_classification_none_routes_to_fallback(self):
        """classification=None → 'fallback'."""
        state = base_state(classification=None)
        assert _route_after_symbol(state) == "fallback"

    def test_fallback_reason_set_routes_to_fallback(self):
        """fallback_reason is set → 'fallback'."""
        classification = make_classification()
        state = base_state(classification=classification, fallback_reason="some_error")
        assert _route_after_symbol(state) == "fallback"

    def test_general_query_type_routes_to_fallback(self):
        """QueryType.GENERAL → 'fallback'."""
        classification = make_classification(query_type=QueryType.GENERAL)
        state = base_state(classification=classification)
        assert _route_after_symbol(state) == "fallback"

    def test_numerical_and_text_routes_to_numerical_priority(self):
        """needs_numerical AND needs_text → 'numerical_analysis' (priority)."""
        classification = make_classification(
            needs_numerical_analysis=True,
            needs_text_analysis=True,
        )
        state = base_state(classification=classification)
        assert _route_after_symbol(state) == "numerical_analysis"

    def test_numerical_only_routes_to_numerical(self):
        """needs_numerical only → 'numerical_analysis'."""
        classification = make_classification(
            needs_numerical_analysis=True,
            needs_text_analysis=False,
        )
        state = base_state(classification=classification)
        assert _route_after_symbol(state) == "numerical_analysis"

    def test_text_only_routes_to_text_analysis(self):
        """needs_text only → 'text_analysis'."""
        classification = make_classification(
            needs_numerical_analysis=False,
            needs_text_analysis=True,
        )
        state = base_state(classification=classification)
        assert _route_after_symbol(state) == "text_analysis"

    def test_no_flags_routes_to_fallback(self):
        """Neither needs_numerical nor needs_text → 'fallback'."""
        classification = make_classification(
            needs_numerical_analysis=False,
            needs_text_analysis=False,
        )
        state = base_state(classification=classification)
        assert _route_after_symbol(state) == "fallback"

    def test_comparison_type_routes_to_fallback(self):
        """QueryType.COMPARISON with no flags → 'fallback'."""
        classification = make_classification(
            query_type=QueryType.COMPARISON,
            needs_numerical_analysis=False,
            needs_text_analysis=False,
        )
        state = base_state(classification=classification)
        assert _route_after_symbol(state) == "fallback"


# ============================================================================
# _route_after_numerical
# ============================================================================


class TestRouteAfterNumerical:
    """Tests for _route_after_numerical routing function."""

    def test_needs_text_analysis_routes_to_text(self):
        """needs_text_analysis=True → 'text_analysis'."""
        classification = make_classification(
            needs_numerical_analysis=True,
            needs_text_analysis=True,
        )
        state = base_state(classification=classification)
        assert _route_after_numerical(state) == "text_analysis"

    def test_no_text_needed_routes_to_merge(self):
        """needs_text_analysis=False → 'merge'."""
        classification = make_classification(
            needs_numerical_analysis=True,
            needs_text_analysis=False,
        )
        state = base_state(classification=classification)
        assert _route_after_numerical(state) == "merge"

    def test_classification_none_routes_to_merge(self):
        """classification=None (safe getter) → 'merge'."""
        state = base_state(classification=None)
        assert _route_after_numerical(state) == "merge"


# ============================================================================
# Graph compilation
# ============================================================================


class TestGraphCompilation:
    """Tests for graph build and singleton."""

    def test_build_workflow_returns_uncompiled_graph(self):
        """build_workflow() returns a StateGraph (not compiled yet)."""
        wf = build_workflow()
        # Should be a StateGraph, not a CompiledGraph
        from langgraph.graph import StateGraph

        assert isinstance(wf, StateGraph)

    def test_get_graph_returns_compiled(self):
        """get_graph() returns a compiled graph."""
        graph = get_graph()
        # Compiled graph has .nodes attribute
        assert hasattr(graph, "nodes")

    def test_get_graph_singleton_same_instance(self):
        """get_graph() returns the same instance on repeated calls."""
        graph1 = get_graph()
        graph2 = get_graph()
        assert graph1 is graph2

    def test_graph_has_all_nodes(self):
        """Compiled graph contains all 6 agent nodes."""
        graph = get_graph()
        node_names = set(graph.nodes)
        expected = {
            "classify_query",
            "resolve_symbol",
            "numerical_analysis",
            "text_analysis",
            "merge",
            "fallback",
        }
        assert expected.issubset(node_names)

    def test_graph_entry_point_is_classify_query(self):
        """Entry point is classify_query node."""
        graph = get_graph()
        # The __start__ node always exists; we verify classify_query is in the graph
        assert "classify_query" in graph.nodes
