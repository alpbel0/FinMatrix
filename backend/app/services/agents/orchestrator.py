"""CrewAI orchestrator for routing chat queries to the right agents."""

from functools import lru_cache
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.schemas.chat import QueryUnderstandingResult, RetrievalAgentResult
from app.schemas.enums import DocumentType, QueryIntent, QueryType
from app.services.agents.code_executor import run_numerical_analysis
from app.services.agents.crewai_adapter import create_agent_or_spec
from app.services.agents.merger import merge_analysis_results
from app.services.agents.query_classifier import classify_query
from app.services.agents.symbol_resolver import resolve_symbol
from app.services.chat_trace_service import ChatPipelineResult
from app.services.data.provider_models import PeriodType
from app.services.utils.logging import logger


def _empty_retrieval() -> RetrievalAgentResult:
    return RetrievalAgentResult(
        chunks=[],
        sources=[],
        has_sufficient_context=False,
        retrieval_confidence=0.0,
        context_total_chars=0,
    )


def build_orchestrator_agent() -> Any:
    """Build the CrewAI orchestrator role or fallback metadata."""
    settings = get_settings()
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


def _query_type_to_intent(query_type: QueryType) -> QueryIntent:
    """Map QueryType to QueryIntent for trace/debug compatibility."""
    mapping = {
        QueryType.NUMERICAL_ANALYSIS: QueryIntent.METRIC,
        QueryType.COMPARISON: QueryIntent.METRIC,
        QueryType.TEXT_ANALYSIS: QueryIntent.SUMMARY,
        QueryType.GENERAL: QueryIntent.GENERIC,
    }
    return mapping.get(query_type, QueryIntent.GENERIC)


async def run_orchestrated_pipeline(
    db: AsyncSession,
    user_id: int,
    session_id: int,
    query: str,
    http_client: httpx.AsyncClient | None = None,
) -> ChatPipelineResult:
    """Run classifier, selected agents, and merger for a chat query."""
    from app.services.agents.text_analyst import run_text_analysis
    from app.services.chat_rag_service import run_document_pipeline

    should_close_client = http_client is None
    client = http_client or httpx.AsyncClient(timeout=get_settings().llm_timeout)

    try:
        classification = await classify_query(query, http_client=client)
        logger.debug(
            "Orchestrator classification: type=%s, needs_text=%s, needs_numerical=%s, symbols=%s",
            classification.query_type,
            classification.needs_text_analysis,
            classification.needs_numerical_analysis,
            classification.symbols,
        )

        if classification.query_type == QueryType.GENERAL:
            return await run_document_pipeline(
                db=db,
                user_id=user_id,
                session_id=session_id,
                query=query,
            )

        resolved_symbol: str | None = None
        if classification.symbols:
            resolved_symbol = await resolve_symbol(
                db,
                classification.symbols[0],
            )

        numerical_result = None
        text_result = None

        if classification.needs_numerical_analysis:
            numerical_result = await run_numerical_analysis(
                db=db,
                query=query,
                symbols=classification.symbols,
                period_type=PeriodType.ANNUAL,
                needs_chart=classification.needs_chart,
                http_client=client,
            )

        if classification.needs_text_analysis:
            text_result = await run_text_analysis(
                db=db,
                user_id=user_id,
                session_id=session_id,
                query=query,
                http_client=client,
            )

        if numerical_result is None and text_result is None:
            return await run_document_pipeline(
                db=db,
                user_id=user_id,
                session_id=session_id,
                query=query,
            )

        response = merge_analysis_results(
            classification=classification,
            resolved_symbol=resolved_symbol,
            numerical_result=numerical_result,
            text_result=text_result,
        )

        understanding = QueryUnderstandingResult(
            normalized_query=query,
            candidate_symbol=classification.symbols[0] if classification.symbols else None,
            document_type=text_result.document_type if text_result else DocumentType.ANY,
            intent=_query_type_to_intent(classification.query_type),
            confidence=classification.confidence,
            suggested_rewrite=None,
        )

        retrieval = (
            text_result and RetrievalAgentResult(
                chunks=[],
                sources=text_result.sources,
                has_sufficient_context=not text_result.insufficient_context,
                retrieval_confidence=text_result.retrieval_confidence,
                context_total_chars=0,
            )
        ) or _empty_retrieval()

        return ChatPipelineResult(
            response=response,
            understanding=understanding,
            resolved_symbol=resolved_symbol,
            retrieval=retrieval,
            memory_context="",
        )
    finally:
        if should_close_client:
            await client.aclose()
