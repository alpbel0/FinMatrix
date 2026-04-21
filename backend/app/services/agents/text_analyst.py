"""CrewAI-ready text analyst built on direct retrieval + response generation."""

import re
from functools import lru_cache
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.schemas.chat import QueryClassificationResult, QueryUnderstandingResult, TextAnalysisResult
from app.schemas.enums import DocumentType
from app.services.agents.crewai_adapter import create_agent_or_spec
from app.services.agents.query_understanding_agent import _heuristic_document_type, _heuristic_intent
from app.services.agents.response_agent import generate_response
from app.services.agents.retrieval_agent import run_retrieval
from app.services.chat_rag_service import (
    enrich_retrieval_sources,
    format_memory_context,
    get_last_messages,
    get_structured_financial_context,
)


def build_text_analyst_agent() -> Any:
    """Build the CrewAI text analyst role or fallback metadata."""
    settings = get_settings()
    return create_agent_or_spec(
        role="FinMatrix Text Analyst",
        goal="Answer Turkish investor questions using only retrieved KAP and report evidence.",
        backstory=(
            "You are a source-disciplined BIST document analyst. "
            "You use FinMatrix retrieval services, preserve citations, and avoid unsupported claims."
        ),
        llm_model=settings.response_agent_model,
    )


@lru_cache(maxsize=1)
def get_text_analyst_agent() -> Any:
    """Return the CrewAI text analyst role lazily."""
    return build_text_analyst_agent()


def _extract_key_points(answer_text: str, max_points: int = 5) -> list[str]:
    """Extract compact key points from a generated answer."""
    points: list[str] = []
    for raw_line in answer_text.splitlines():
        line = raw_line.strip().strip("*-• ").strip()
        if not line or len(line) < 20:
            continue
        if line.endswith(":"):
            continue
        points.append(re.sub(r"\s+", " ", line))
        if len(points) >= max_points:
            break
    return points


def _build_understanding(
    query: str,
    resolved_symbols: list[str] | None,
    classification: QueryClassificationResult | None,
) -> QueryUnderstandingResult:
    """Build a lightweight understanding object without re-running LLM analysis."""
    resolved_symbol = resolved_symbols[0] if resolved_symbols else None
    confidence = classification.confidence if classification is not None else 0.3
    return QueryUnderstandingResult(
        normalized_query=query.strip(),
        candidate_symbol=resolved_symbol,
        document_type=_heuristic_document_type(query),
        intent=_heuristic_intent(query),
        confidence=confidence,
        suggested_rewrite=None,
    )


async def run_text_analysis(
    *,
    db: AsyncSession,
    user_id: int,
    session_id: int,
    query: str,
    resolved_symbols: list[str] | None,
    classification: QueryClassificationResult | None,
    http_client: httpx.AsyncClient | None = None,
) -> TextAnalysisResult:
    """Run text analysis using pre-resolved symbols and graph classification state."""
    settings = get_settings()
    understanding = _build_understanding(query, resolved_symbols, classification)
    resolved_symbol = resolved_symbols[0] if resolved_symbols else None

    memory_messages = await get_last_messages(
        db=db,
        session_id=session_id,
        limit=settings.chat_memory_window,
    )
    memory_context = format_memory_context(memory_messages)

    should_close_client = http_client is None
    client = http_client or httpx.AsyncClient(timeout=settings.llm_timeout)

    try:
        retrieval = await run_retrieval(
            query=query,
            resolved_symbol=resolved_symbol,
            document_type=understanding.document_type,
            understanding=understanding,
        )
        retrieval = await enrich_retrieval_sources(db, retrieval)
        structured_financial_context = await get_structured_financial_context(
            db=db,
            symbol=resolved_symbol,
            intent=understanding.intent,
        )
        response = await generate_response(
            original_query=query,
            understanding=understanding,
            retrieval=retrieval,
            memory_context=memory_context,
            structured_financial_context=structured_financial_context,
            http_client=client,
        )
        response.stock_symbol = resolved_symbol

        return TextAnalysisResult(
            answer_text=response.answer_text,
            key_points=_extract_key_points(response.answer_text),
            sources=response.sources,
            stock_symbol=response.stock_symbol,
            document_type=response.document_type or DocumentType.ANY,
            insufficient_context=response.insufficient_context,
            confidence_note=response.confidence_note,
            retrieval_confidence=retrieval.retrieval_confidence,
        )
    finally:
        if should_close_client:
            await client.aclose()
