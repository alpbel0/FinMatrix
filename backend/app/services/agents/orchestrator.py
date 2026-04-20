"""CrewAI orchestrator for routing chat queries to the right agents."""

from functools import lru_cache
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.schemas.chat import (
    QueryUnderstandingResult,
    RAGResponse,
    RetrievalAgentResult,
)
from app.schemas.enums import DocumentType, QueryIntent
from app.services.agents.graph import AgentState, get_graph
from app.services.chat_trace_service import ChatPipelineResult
from app.services.utils.logging import logger


def _empty_retrieval() -> RetrievalAgentResult:
    return RetrievalAgentResult(
        chunks=[],
        sources=[],
        has_sufficient_context=False,
        retrieval_confidence=0.0,
        context_total_chars=0,
    )


def _build_minimal_understanding(
    response: RAGResponse | None, query: str
) -> QueryUnderstandingResult:
    """Build a minimal QueryUnderstandingResult from graph output for trace compatibility."""
    if response is not None and response.stock_symbol:
        doc_type = response.document_type or DocumentType.ANY
        intent_map = {
            DocumentType.FR: QueryIntent.METRIC,
            DocumentType.FAR: QueryIntent.SUMMARY,
            DocumentType.ANY: QueryIntent.GENERIC,
        }
        intent = intent_map.get(doc_type, QueryIntent.GENERIC)
        return QueryUnderstandingResult(
            normalized_query=query,
            candidate_symbol=response.stock_symbol,
            document_type=doc_type,
            intent=intent,
            confidence=1.0,
            suggested_rewrite=None,
        )
    return QueryUnderstandingResult(
        normalized_query=query,
        candidate_symbol=None,
        document_type=DocumentType.ANY,
        intent=QueryIntent.GENERIC,
        confidence=0.0,
        suggested_rewrite=None,
    )


def build_orchestrator_agent() -> Any:
    """Build the CrewAI orchestrator role or fallback metadata."""
    settings = get_settings()
    from app.services.agents.crewai_adapter import create_agent_or_spec

    return create_agent_or_spec(
        role="FinMatrix Orchestrator",
        goal="Route BIST investor queries to the correct analysis agent.",
        backstory="Expert in Turkish financial query routing and multi-agent coordination.",
        llm_model=settings.orchestrator_model,
    )


@lru_cache(maxsize=1)
def get_orchestrator_agent() -> Any:
    """Return the CrewAI orchestrator role lazily."""
    return build_orchestrator_agent()


def _log_graph_summary(
    node_history: list[Any], fallback_reason: str | None
) -> None:
    """Log a summary of the graph execution for trace/debug purposes."""
    node_count = len(node_history)
    total_ms = sum(entry.get("duration_ms", 0) for entry in node_history)
    logger.info(
        "graph_summary: nodes=%d, total_ms=%.1f, fallback_reason=%s",
        node_count,
        total_ms,
        fallback_reason,
    )


async def run_orchestrated_pipeline(
    db: AsyncSession,
    user_id: int,
    session_id: int,
    query: str,
    http_client: httpx.AsyncClient | None = None,
) -> ChatPipelineResult:
    """Run the LangGraph orchestration pipeline for a chat query."""
    initial_state: AgentState = {
        "query": query,
        "user_id": user_id,
        "session_id": session_id,
        "http_client": http_client,
        "node_history": [],
    }

    graph = get_graph()
    final_state = await graph.ainvoke(initial_state)

    response = final_state.get("response")
    resolved_symbol = final_state.get("resolved_symbol")
    node_history = final_state.get("node_history", [])
    fallback_reason = final_state.get("fallback_reason")

    _log_graph_summary(node_history, fallback_reason)

    understanding = _build_minimal_understanding(response, query)

    if response is not None and response.sources:
        retrieval = RetrievalAgentResult(
            chunks=[],
            sources=response.sources,
            has_sufficient_context=not response.insufficient_context,
            retrieval_confidence=0.0,
            context_total_chars=0,
        )
    else:
        retrieval = _empty_retrieval()

    return ChatPipelineResult(
        response=response,
        understanding=understanding,
        resolved_symbol=resolved_symbol,
        retrieval=retrieval,
        memory_context="",
        node_history=node_history,
        fallback_reason=fallback_reason,
    )
