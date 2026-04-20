"""Chat RAG service for orchestrating the full RAG pipeline."""

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.chat import ChatMessage, ChatSession
from app.models.income_statement import IncomeStatement
from app.models.kap_report import KapReport
from app.models.stock import Stock
from app.schemas.chat import QueryUnderstandingResult, RAGResponse, RetrievalAgentResult
from app.schemas.enums import DocumentType, QueryIntent
from app.services.agents.query_understanding_agent import analyze_query, is_greeting
from app.services.agents.retrieval_agent import run_retrieval
from app.services.agents.response_agent import GREETING_RESPONSE, generate_response
from app.services.agents.symbol_resolver import resolve_symbol
from app.services.chat_trace_service import ChatPipelineResult
from app.services.utils.logging import logger


async def get_last_messages(
    db: AsyncSession,
    session_id: int,
    limit: int = 5,
) -> list[ChatMessage]:
    """Get last N messages from a chat session."""
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
    )
    return list(reversed(result.scalars().all()))


def format_memory_context(messages: list[ChatMessage]) -> str:
    """Format messages for memory context."""
    if not messages:
        return ""

    formatted = []
    for message in messages:
        role = "Kullanıcı" if message.role == "user" else "Asistan"
        formatted.append(f"{role}: {message.content[:200]}")

    return "\n".join(formatted)


def _format_money(value: float | None) -> str:
    """Format TRY financial statement values for LLM grounding."""
    if value is None:
        return "yok"
    return f"{value:,.0f} TRY".replace(",", ".")


async def get_structured_financial_context(
    db: AsyncSession,
    symbol: str | None,
    intent: QueryIntent,
) -> str:
    """Build a verified structured metric block for metric-oriented answers."""
    if not symbol or intent != QueryIntent.METRIC:
        return ""

    result = await db.execute(
        select(IncomeStatement)
        .join(Stock, Stock.id == IncomeStatement.stock_id)
        .where(Stock.symbol == symbol)
        .order_by(IncomeStatement.statement_date.desc())
    )
    statements = list(result.scalars().all())
    if not statements:
        return ""

    latest_by_period: dict[str, IncomeStatement] = {}
    for statement in statements:
        if statement.period_type not in latest_by_period:
            latest_by_period[statement.period_type] = statement

    lines = [
        f"DOGRULANMIS DB METRIKLERI - {symbol}",
        "Kaynak tipi: Yapilandirilmis finansal tablo veritabani.",
        "Kural: Net kar sorularinda net_income degerini kullan; revenue/hasılat degerini net kar gibi yorumlama.",
    ]
    for period_type in ("annual", "quarterly"):
        statement = latest_by_period.get(period_type)
        if statement is None:
            continue
        lines.append(
            f"- {period_type} {statement.statement_date}: "
            f"revenue={_format_money(statement.revenue)}; "
            f"net_income={_format_money(statement.net_income)}; "
            f"source={statement.source}"
        )

    return "\n".join(lines)


async def enrich_retrieval_sources(
    db: AsyncSession,
    retrieval: RetrievalAgentResult,
) -> RetrievalAgentResult:
    """Backfill source URLs from KapReport when vector metadata is incomplete."""
    report_ids = {
        source.kap_report_id
        for source in retrieval.sources
        if source.kap_report_id and not source.source_url
    }
    if not report_ids:
        return retrieval

    result = await db.execute(
        select(KapReport.id, KapReport.source_url)
        .where(KapReport.id.in_(report_ids))
    )
    source_url_map = {report_id: source_url or "" for report_id, source_url in result}

    for source in retrieval.sources:
        if not source.source_url:
            source.source_url = source_url_map.get(source.kap_report_id, "")

    for chunk in retrieval.chunks:
        metadata = chunk.get("metadata", {})
        kap_report_id = metadata.get("kap_report_id")
        if kap_report_id and not metadata.get("source_url"):
            metadata["source_url"] = source_url_map.get(kap_report_id, "")

    return retrieval


def _empty_retrieval_result() -> RetrievalAgentResult:
    return RetrievalAgentResult(
        chunks=[],
        sources=[],
        has_sufficient_context=False,
        retrieval_confidence=0.0,
        context_total_chars=0,
    )


def _generic_understanding(query: str) -> QueryUnderstandingResult:
    return QueryUnderstandingResult(
        normalized_query=query,
        candidate_symbol=None,
        document_type=DocumentType.ANY,
        intent=QueryIntent.GENERIC,
        confidence=0.0,
    )


def _pipeline_result(
    *,
    response: RAGResponse,
    understanding: QueryUnderstandingResult,
    resolved_symbol: str | None,
    retrieval: RetrievalAgentResult,
    memory_context: str,
) -> ChatPipelineResult:
    return ChatPipelineResult(
        response=response,
        understanding=understanding,
        resolved_symbol=resolved_symbol,
        retrieval=retrieval,
        memory_context=memory_context,
        node_history=[],
        fallback_reason=None,
    )


async def run_document_pipeline(
    db: AsyncSession,
    user_id: int,
    session_id: int,
    query: str,
) -> ChatPipelineResult:
    """Run the legacy document-first RAG pipeline."""
    settings = get_settings()

    session_result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id,
        )
    )
    session = session_result.scalar_one_or_none()
    if not session:
        logger.warning("Session not found or access denied: session_id=%s, user_id=%s", session_id, user_id)
        return _pipeline_result(
            response=RAGResponse(
                answer_text="Oturum bulunamadı. Lütfen yeni bir oturum başlatın.",
                sources=[],
                stock_symbol=None,
                document_type=DocumentType.ANY,
                insufficient_context=True,
            ),
            understanding=_generic_understanding(query),
            resolved_symbol=None,
            retrieval=_empty_retrieval_result(),
            memory_context="",
        )

    memory_messages = await get_last_messages(
        db=db,
        session_id=session_id,
        limit=settings.chat_memory_window,
    )
    memory_context = format_memory_context(memory_messages)
    logger.debug("Memory context: %s messages", len(memory_messages))

    async with httpx.AsyncClient(timeout=settings.llm_timeout) as http_client:
        if is_greeting(query):
            logger.debug("Greeting detected (rule-based)")
            understanding = QueryUnderstandingResult(
                normalized_query=query,
                candidate_symbol=None,
                document_type=DocumentType.ANY,
                intent=QueryIntent.GENERIC,
                confidence=1.0,
            )
            return _pipeline_result(
                response=RAGResponse(
                    answer_text=GREETING_RESPONSE,
                    sources=[],
                    stock_symbol=None,
                    document_type=DocumentType.ANY,
                    confidence_note="Sistem belge odaklı çalışmaktadır.",
                    insufficient_context=False,
                ),
                understanding=understanding,
                resolved_symbol=None,
                retrieval=_empty_retrieval_result(),
                memory_context=memory_context,
            )

        understanding = await analyze_query(
            query=query,
            http_client=http_client,
        )
        logger.debug(
            "Query understanding: intent=%s, symbol=%s",
            understanding.intent,
            understanding.candidate_symbol,
        )

        resolved_symbol = await resolve_symbol(
            db=db,
            candidate_symbol=understanding.candidate_symbol,
        )
        logger.debug("Resolved symbol: %s", resolved_symbol)

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
        logger.debug(
            "Retrieval: %s chunks, sufficient=%s",
            len(retrieval.chunks),
            retrieval.has_sufficient_context,
        )

        response = await generate_response(
            original_query=query,
            understanding=understanding,
            retrieval=retrieval,
            memory_context=memory_context,
            structured_financial_context=structured_financial_context,
            http_client=http_client,
        )
        response.stock_symbol = resolved_symbol

        return _pipeline_result(
            response=response,
            understanding=understanding,
            resolved_symbol=resolved_symbol,
            retrieval=retrieval,
            memory_context=memory_context,
        )


async def run_chat_pipeline(
    db: AsyncSession,
    user_id: int,
    session_id: int,
    query: str,
) -> ChatPipelineResult:
    """Run the public chat pipeline through the orchestrator layer."""
    session_result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id,
        )
    )
    session = session_result.scalar_one_or_none()
    if not session:
        logger.warning("Session not found or access denied: session_id=%s, user_id=%s", session_id, user_id)
        return _pipeline_result(
            response=RAGResponse(
                answer_text="Oturum bulunamadÄ±. LÃ¼tfen yeni bir oturum baÅŸlatÄ±n.",
                sources=[],
                stock_symbol=None,
                document_type=DocumentType.ANY,
                insufficient_context=True,
            ),
            understanding=_generic_understanding(query),
            resolved_symbol=None,
            retrieval=_empty_retrieval_result(),
            memory_context="",
        )

    from app.services.agents.orchestrator import run_orchestrated_pipeline

    return await run_orchestrated_pipeline(
        db=db,
        user_id=user_id,
        session_id=session_id,
        query=query,
    )


async def process_chat_query(
    db: AsyncSession,
    user_id: int,
    session_id: int,
    query: str,
) -> RAGResponse:
    """Compatibility wrapper that returns only the final response."""
    pipeline_result = await run_chat_pipeline(
        db=db,
        user_id=user_id,
        session_id=session_id,
        query=query,
    )
    return pipeline_result.response


async def create_chat_session(
    db: AsyncSession,
    user_id: int,
    title: str | None = None,
) -> ChatSession:
    """Create a new chat session."""
    session = ChatSession(
        user_id=user_id,
        title=title,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def get_user_sessions(
    db: AsyncSession,
    user_id: int,
) -> list[ChatSession]:
    """Get all chat sessions for a user."""
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == user_id)
        .order_by(ChatSession.created_at.desc())
    )
    return list(result.scalars().all())


async def save_message(
    db: AsyncSession,
    session_id: int,
    role: str,
    content: str,
    sources_metadata: list | None = None,
) -> ChatMessage:
    """Save a chat message to the database."""
    message = ChatMessage(
        session_id=session_id,
        role=role,
        content=content,
        sources_metadata=sources_metadata or [],
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)
    return message
