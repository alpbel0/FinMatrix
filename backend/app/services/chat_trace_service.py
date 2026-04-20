"""Structured trace persistence for chat/RAG pipeline runs."""

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.chat_trace import ChatTrace
from app.schemas.chat import QueryUnderstandingResult, RAGResponse, RetrievalAgentResult


def _truncate_text(value: str, max_length: int = 500) -> str:
    return value[:max_length] if len(value) > max_length else value


def _summarize_sources(sources: list[Any]) -> list[dict[str, Any]]:
    summarized: list[dict[str, Any]] = []
    for source in sources[:3]:
        if hasattr(source, "model_dump"):
            data = source.model_dump(mode="json")
        else:
            data = dict(source)
        data["chunk_preview"] = _truncate_text(data.get("chunk_preview", ""), 160)
        summarized.append(data)
    return summarized


def _build_retrieval_payload(retrieval: RetrievalAgentResult) -> dict[str, Any]:
    chunks_preview = []
    for chunk in retrieval.chunks[:2]:
        metadata = dict(chunk.get("metadata", {}))
        chunks_preview.append(
            {
                "score": chunk.get("score"),
                "chunk_preview": _truncate_text(chunk.get("chunk_text", ""), 200),
                "metadata": {
                    "kap_report_id": metadata.get("kap_report_id"),
                    "stock_symbol": metadata.get("stock_symbol"),
                    "filing_type": metadata.get("filing_type"),
                    "source_url": metadata.get("source_url"),
                },
            }
        )

    return {
        "chunk_count": len(retrieval.chunks),
        "retrieval_confidence": retrieval.retrieval_confidence,
        "context_total_chars": retrieval.context_total_chars,
        "has_sufficient_context": retrieval.has_sufficient_context,
        "chunks_preview": chunks_preview,
    }


def _build_response_payload(response: RAGResponse) -> dict[str, Any]:
    return {
        "answer_preview": _truncate_text(response.answer_text, 300),
        "source_count": len(response.sources),
        "stock_symbol": response.stock_symbol,
        "document_type": response.document_type.value,
        "confidence_note": response.confidence_note,
        "insufficient_context": response.insufficient_context,
    }


@dataclass
class ChatPipelineResult:
    """Internal pipeline result with debug context for tracing."""

    response: RAGResponse | None
    understanding: QueryUnderstandingResult
    resolved_symbol: str | None
    retrieval: RetrievalAgentResult
    memory_context: str
    node_history: list[dict[str, Any]] = field(default_factory=list)
    fallback_reason: str | None = None


def _apply_graph_debug_payload(trace: ChatTrace, pipeline_result: ChatPipelineResult) -> None:
    trace.graph_node_history = pipeline_result.node_history
    trace.graph_fallback_reason = pipeline_result.fallback_reason


async def create_chat_trace(
    db: AsyncSession,
    *,
    session_id: int,
    user_id: int,
    user_message_id: int | None,
    original_query: str,
) -> ChatTrace:
    trace = ChatTrace(
        session_id=session_id,
        user_id=user_id,
        user_message_id=user_message_id,
        original_query=original_query,
        status="STARTED",
    )
    db.add(trace)
    await db.commit()
    await db.refresh(trace)
    return trace


async def finalize_chat_trace_success(
    db: AsyncSession,
    *,
    trace: ChatTrace,
    pipeline_result: ChatPipelineResult,
    assistant_message_id: int | None,
    duration_ms: int,
) -> ChatTrace:
    settings = get_settings()
    response = pipeline_result.response
    understanding = pipeline_result.understanding
    retrieval = pipeline_result.retrieval

    trace.assistant_message_id = assistant_message_id
    trace.status = "SUCCESS"
    _apply_graph_debug_payload(trace, pipeline_result)
    trace.normalized_query = understanding.normalized_query
    trace.candidate_symbol = understanding.candidate_symbol
    trace.resolved_symbol = pipeline_result.resolved_symbol
    trace.document_type = understanding.document_type.value
    trace.intent = understanding.intent.value
    trace.query_understanding_model = settings.query_understanding_model
    trace.response_model = settings.response_agent_model
    trace.memory_context_preview = _truncate_text(pipeline_result.memory_context, 500) if pipeline_result.memory_context else None
    trace.retrieved_chunk_count = len(retrieval.chunks)
    trace.retrieval_confidence = retrieval.retrieval_confidence
    trace.context_total_chars = retrieval.context_total_chars
    trace.has_sufficient_context = retrieval.has_sufficient_context
    trace.sources_metadata = _summarize_sources(response.sources)
    trace.understanding_payload = understanding.model_dump(mode="json")
    trace.retrieval_payload = _build_retrieval_payload(retrieval)
    trace.response_payload = _build_response_payload(response)
    trace.error_message = None
    trace.duration_ms = duration_ms

    await db.commit()
    await db.refresh(trace)
    return trace


async def finalize_chat_trace_failure(
    db: AsyncSession,
    *,
    trace: ChatTrace,
    error_message: str,
    duration_ms: int,
    pipeline_result: ChatPipelineResult | None = None,
) -> ChatTrace:
    trace.status = "FAILED"
    trace.error_message = _truncate_text(error_message, 500)
    trace.duration_ms = duration_ms
    trace.sources_metadata = []
    trace.response_payload = {}

    if pipeline_result is not None:
        understanding = pipeline_result.understanding
        retrieval = pipeline_result.retrieval
        _apply_graph_debug_payload(trace, pipeline_result)
        trace.normalized_query = understanding.normalized_query
        trace.candidate_symbol = understanding.candidate_symbol
        trace.resolved_symbol = pipeline_result.resolved_symbol
        trace.document_type = understanding.document_type.value
        trace.intent = understanding.intent.value
        trace.memory_context_preview = _truncate_text(pipeline_result.memory_context, 500) if pipeline_result.memory_context else None
        trace.retrieved_chunk_count = len(retrieval.chunks)
        trace.retrieval_confidence = retrieval.retrieval_confidence
        trace.context_total_chars = retrieval.context_total_chars
        trace.has_sufficient_context = retrieval.has_sufficient_context
        trace.understanding_payload = understanding.model_dump(mode="json")
        trace.retrieval_payload = _build_retrieval_payload(retrieval)
        if pipeline_result.response is not None:
            trace.sources_metadata = _summarize_sources(pipeline_result.response.sources)
            trace.response_payload = _build_response_payload(pipeline_result.response)

    await db.commit()
    await db.refresh(trace)
    return trace
