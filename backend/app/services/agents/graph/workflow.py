"""LangGraph state machine for FinMatrix agent orchestration."""

from typing import Any, Literal

from langgraph.graph import StateGraph, END

from app.schemas.enums import QueryType
from app.services.agents.graph.nodes import (
    classify_query_node,
    fallback_node,
    merge_node,
    numerical_analysis_node,
    resolve_symbol_node,
    text_analysis_node,
)
from app.services.agents.graph.state import AgentState


# ---------------------------------------------------------------------------
# Routing helpers
# ---------------------------------------------------------------------------


def _route_after_symbol(state: AgentState) -> Literal["fallback", "numerical_analysis", "text_analysis"]:
    """Route after symbol resolution based on classification result."""
    classification = state.get("classification")
    fallback_reason = state.get("fallback_reason")

    # classification is None OR fallback_reason is set → fallback
    if classification is None or fallback_reason is not None:
        return "fallback"

    # QueryType.GENERAL → fallback
    if classification.query_type == QueryType.GENERAL:
        return "fallback"

    # needs_numerical AND needs_text → numerical_analysis (priority)
    if classification.needs_numerical_analysis and classification.needs_text_analysis:
        return "numerical_analysis"

    # needs_numerical → numerical_analysis
    if classification.needs_numerical_analysis:
        return "numerical_analysis"

    # needs_text → text_analysis
    if classification.needs_text_analysis:
        return "text_analysis"

    # default → fallback
    return "fallback"


def _route_after_numerical(state: AgentState) -> Literal["text_analysis", "merge"]:
    """Route after numerical analysis based on whether text analysis is also needed."""
    classification = state.get("classification")

    # Safe getter — classification should never be None here, but we guard anyway
    if classification is not None and classification.needs_text_analysis:
        return "text_analysis"

    # default → merge
    return "merge"


# ---------------------------------------------------------------------------
# Workflow builder
# ---------------------------------------------------------------------------


def build_workflow() -> StateGraph:
    """Build the FinMatrix agent StateGraph with all nodes and edges.

    The graph flow:
        classify_query → resolve_symbol → routing
                                              ├→ numerical_analysis → routing
                                              │                                    └→ merge → END
                                              ├→ text_analysis ──────────────────┘
                                              └→ fallback → END
    """
    graph = StateGraph(AgentState)

    # Add all nodes
    graph.add_node("classify_query", classify_query_node)
    graph.add_node("resolve_symbol", resolve_symbol_node)
    graph.add_node("numerical_analysis", numerical_analysis_node)
    graph.add_node("text_analysis", text_analysis_node)
    graph.add_node("merge", merge_node)
    graph.add_node("fallback", fallback_node)

    # Entry point
    graph.set_entry_point("classify_query")

    # Edges
    graph.add_edge("classify_query", "resolve_symbol")
    graph.add_conditional_edges("resolve_symbol", _route_after_symbol)
    graph.add_conditional_edges("numerical_analysis", _route_after_numerical)
    graph.add_edge("text_analysis", "merge")
    graph.add_edge("merge", END)
    graph.add_edge("fallback", END)

    return graph


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_compiled_graph: Any = None


def get_graph() -> Any:
    """Return the compiled LangGraph (singleton, compiled on first call)."""
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_workflow().compile()
    return _compiled_graph
