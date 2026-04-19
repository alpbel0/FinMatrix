"""CrewAI-ready text analyst wrapper around the document RAG text flow."""

import re
from typing import Any
from functools import lru_cache

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.schemas.chat import TextAnalysisResult
from app.services.agents.crewai_adapter import create_agent_or_spec
from app.services.chat_rag_service import run_document_pipeline


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


async def run_text_analysis(
    *,
    db: AsyncSession,
    user_id: int,
    session_id: int,
    query: str,
    http_client: httpx.AsyncClient | None = None,
) -> TextAnalysisResult:
    """Run the existing RAG text pipeline and package text analyst output.

    The optional http_client is reserved for future direct tool calls; the current
    pipeline owns a bounded HTTP client internally.
    """
    _ = http_client
    pipeline_result = await run_document_pipeline(
        db=db,
        user_id=user_id,
        session_id=session_id,
        query=query,
    )
    response = pipeline_result.response

    return TextAnalysisResult(
        answer_text=response.answer_text,
        key_points=_extract_key_points(response.answer_text),
        sources=response.sources,
        stock_symbol=response.stock_symbol,
        document_type=response.document_type,
        insufficient_context=response.insufficient_context,
        confidence_note=response.confidence_note,
        retrieval_confidence=pipeline_result.retrieval.retrieval_confidence,
    )
