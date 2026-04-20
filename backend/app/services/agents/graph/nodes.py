"""LangGraph node wrappers for FinMatrix agent orchestration.

Each node wraps an existing service call, records a NodeTraceEntry in
node_history, and returns a partial dict that LangGraph merges into state.
Nodes never raise — all exceptions are caught and converted to graceful
error/skipped entries with an appropriate reason_code.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Literal

from app.database import AsyncSessionLocal
from app.services.agents.code_executor import run_numerical_analysis
from app.services.agents.merger import merge_analysis_results
from app.services.agents.query_classifier import classify_query
from app.services.agents.symbol_resolver import resolve_symbol

if TYPE_CHECKING:
    from app.services.agents.graph.state import AgentState, NodeTraceEntry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _start_trace() -> float:
    """Record the current time in seconds (for duration measurement)."""
    return time.time()


def _make_entry(
    node: str,
    start: float,
    status: Literal["ok", "error", "skipped"],
    reason_code: str | None = None,
) -> "NodeTraceEntry":
    """Build a NodeTraceEntry from a start time and outcome."""
    from app.services.agents.graph.state import NodeTraceEntry

    return NodeTraceEntry(
        node=node,
        status=status,
        duration_ms=(time.time() - start) * 1000,
        reason_code=reason_code,
    )


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------


async def classify_query_node(state: "AgentState") -> dict:
    """Classify the user query (fast path → heuristic, slow path → LLM).

    Sets ``classification`` and ``fallback_reason`` in state on error.
    """
    node_name = "classify_query"
    start = _start_trace()

    try:
        result = await classify_query(
            state["query"],
            http_client=state.get("http_client"),
        )
        return {
            "classification": result,
            "node_history": [_make_entry(node_name, start, "ok")],
        }
    except Exception:
        return {
            "classification": None,
            "fallback_reason": "classification_failed",
            "node_history": [
                _make_entry(node_name, start, "error", "classification_failed")
            ],
        }


async def resolve_symbol_node(state: "AgentState") -> dict:
    """Resolve the first candidate symbol from the classification result.

    Skips when ``classification`` is absent or its ``symbols`` list is empty.
    Sets ``resolved_symbol`` to None on not-found; sets ``fallback_reason``
    when an unexpected error occurs.
    """
    node_name = "resolve_symbol"
    start = _start_trace()

    classification = state.get("classification")
    if not classification or not classification.symbols:
        return {
            "resolved_symbol": None,
            "node_history": [_make_entry(node_name, start, "skipped", "no_symbols")],
        }

    try:
        async with AsyncSessionLocal() as db:
            symbol = await resolve_symbol(db, classification.symbols[0])

        if symbol is None:
            return {
                "resolved_symbol": None,
                "node_history": [
                    _make_entry(node_name, start, "skipped", "symbol_not_found")
                ],
            }

        return {
            "resolved_symbol": symbol,
            "node_history": [_make_entry(node_name, start, "ok")],
        }
    except Exception:
        return {
            "resolved_symbol": None,
            "fallback_reason": "symbol_resolve_error",
            "node_history": [
                _make_entry(node_name, start, "error", "symbol_resolve_error")
            ],
        }


async def numerical_analysis_node(state: "AgentState") -> dict:
    """Run deterministic financial metrics analysis.

    Skips when ``resolved_symbol`` is absent. Passes the already-resolved
    symbol to bypass the internal resolve_symbol call inside
    run_numerical_analysis.
    """
    node_name = "numerical_analysis"
    start = _start_trace()

    resolved_symbol = state.get("resolved_symbol")
    if not resolved_symbol:
        return {
            "numerical_result": None,
            "node_history": [
                _make_entry(node_name, start, "skipped", "no_symbol")
            ],
        }

    classification = state.get("classification")
    needs_chart = bool(classification.needs_chart) if classification else False

    try:
        async with AsyncSessionLocal() as db:
            result = await run_numerical_analysis(
                db,
                state["query"],
                symbols=[resolved_symbol],
                needs_chart=needs_chart,
                http_client=state.get("http_client"),
            )
        return {
            "numerical_result": result,
            "node_history": [_make_entry(node_name, start, "ok")],
        }
    except Exception:
        return {
            "numerical_result": None,
            "node_history": [
                _make_entry(node_name, start, "error", "numerical_failed")
            ],
        }


async def text_analysis_node(state: "AgentState") -> dict:
    """Run KAP document text analysis (RAG-backed).

    Uses ``user_id`` and ``session_id`` from state; creates its own DB
    session via AsyncSessionLocal.
    """
    node_name = "text_analysis"
    start = _start_trace()

    # Local import to avoid circular dependency at module level
    from app.services.agents.text_analyst import run_text_analysis

    try:
        async with AsyncSessionLocal() as db:
            result = await run_text_analysis(
                db=db,
                user_id=state["user_id"],
                session_id=state["session_id"],
                query=state["query"],
                http_client=state.get("http_client"),
            )
        return {
            "text_result": result,
            "node_history": [_make_entry(node_name, start, "ok")],
        }
    except Exception:
        return {
            "text_result": None,
            "node_history": [
                _make_entry(node_name, start, "error", "text_analysis_failed")
            ],
        }


async def merge_node(state: "AgentState") -> dict:
    """Merge numerical and text analysis results into a final RAGResponse.

    This is a synchronous function; no await needed.
    """
    node_name = "merge"
    start = _start_trace()

    try:
        result = merge_analysis_results(
            classification=state.get("classification"),
            resolved_symbol=state.get("resolved_symbol"),
            numerical_result=state.get("numerical_result"),
            text_result=state.get("text_result"),
        )
        return {
            "response": result,
            "node_history": [_make_entry(node_name, start, "ok")],
        }
    except Exception:
        return {
            "response": None,
            "node_history": [_make_entry(node_name, start, "error", "merge_failed")],
        }


async def fallback_node(state: "AgentState") -> dict:
    """Run the legacy document-first RAG pipeline as a last resort.

    Triggered when any earlier node set ``fallback_reason``. Uses
    ``user_id``, ``session_id``, and ``query`` from state.
    """
    node_name = "fallback"
    start = _start_trace()

    # Local import to avoid circular dependency at module level
    from app.services.chat_rag_service import run_document_pipeline

    try:
        async with AsyncSessionLocal() as db:
            pipeline_result = await run_document_pipeline(
                db,
                user_id=state["user_id"],
                session_id=state["session_id"],
                query=state["query"],
            )
        return {
            "response": pipeline_result.response,
            "node_history": [
                _make_entry(node_name, start, "ok", state.get("fallback_reason"))
            ],
        }
    except Exception:
        return {
            "response": None,
            "node_history": [
                _make_entry(node_name, start, "error", "fallback_failed")
            ],
        }
