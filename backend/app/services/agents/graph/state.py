"""LangGraph Agent State definitions."""

import operator
from typing import Annotated, Literal, TypedDict

import httpx

from app.schemas.chat import (
    NumericalAnalysisResult,
    QueryClassificationResult,
    RAGResponse,
    TextAnalysisResult,
)


class NodeTraceEntry(TypedDict):
    """Single node execution trace record.

    Attributes:
        node: Name of the node that was executed (e.g., "classify_query").
        status: Execution outcome — "ok", "error", or "skipped".
        duration_ms: How long the node took to execute in milliseconds.
        reason_code: Optional code explaining why this status occurred
            (e.g., "fallback", "symbol_not_resolved", "classification_failed").
    """

    node: str
    status: Literal["ok", "error", "skipped"]
    duration_ms: float
    reason_code: str | None


class AgentState(TypedDict, total=False):
    """LangGraph state for the FinMatrix orchestration graph.

    All fields are carried through the graph nodes. ``node_history`` uses
    ``operator.add`` so that multiple concurrent nodes can append without
    overwriting each other.

    Attributes:
        query: Original user query string.
        user_id: ID of the user making the request.
        session_id: Active chat session ID.
        http_client: Shared async HTTP client. Nodes create their own if None.
        classification: Query classification result from classify_query_node.
        resolved_symbol: Canonical symbol after resolve_symbol_node.
        text_result: Text analysis result from text_analysis_node.
        numerical_result: Numerical analysis result from numerical_analysis_node.
        response: Final merged response from merge_node or fallback_node.
        fallback_reason: Why the pipeline fell back to the document pipeline.
        node_history: Ordered list of all node execution traces.
    """

    query: str
    user_id: int
    session_id: int
    http_client: httpx.AsyncClient | None
    classification: QueryClassificationResult | None
    resolved_symbol: str | None
    text_result: TextAnalysisResult | None
    numerical_result: NumericalAnalysisResult | None
    response: RAGResponse | None
    fallback_reason: str | None
    node_history: Annotated[list[NodeTraceEntry], operator.add]
