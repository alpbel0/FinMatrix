"""Chat RAG service for orchestrating the full RAG pipeline.

This service coordinates:
1. Symbol resolution
2. Query understanding
3. Retrieval
4. Response generation

Key features:
- Memory context (last N messages)
- Full pipeline orchestration
- Error handling and fallback
"""

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.chat import ChatMessage, ChatSession
from app.models.kap_report import KapReport
from app.schemas.chat import RAGResponse, RetrievalAgentResult
from app.schemas.enums import DocumentType, QueryIntent
from app.services.agents.query_understanding_agent import analyze_query, is_greeting
from app.services.agents.retrieval_agent import run_retrieval
from app.services.agents.response_agent import GREETING_RESPONSE, generate_response
from app.services.agents.symbol_resolver import resolve_symbol
from app.services.utils.logging import logger


# ============================================================================
# Helper Functions
# ============================================================================


async def get_last_messages(
    db: AsyncSession,
    session_id: int,
    limit: int = 5,
) -> list[ChatMessage]:
    """Get last N messages from a chat session.

    Args:
        db: AsyncSession for database queries
        session_id: Chat session ID
        limit: Number of messages to retrieve

    Returns:
        List of ChatMessage objects (oldest first)
    """
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
    )
    messages = list(reversed(result.scalars().all()))
    return messages


def format_memory_context(messages: list[ChatMessage]) -> str:
    """Format messages for memory context.

    Args:
        messages: List of ChatMessage objects

    Returns:
        Formatted context string
    """
    if not messages:
        return ""

    formatted = []
    for msg in messages:
        role = "Kullanıcı" if msg.role == "user" else "Asistan"
        formatted.append(f"{role}: {msg.content[:200]}")  # Truncate long messages

    return "\n".join(formatted)


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


# ============================================================================
# Core Service Functions
# ============================================================================


async def process_chat_query(
    db: AsyncSession,
    user_id: int,
    session_id: int,
    query: str,
) -> RAGResponse:
    """Process a chat query through the full RAG pipeline.

    Flow:
    1. Validate session ownership
    2. Get memory context (last N messages)
    3. Quick greeting check (rule-based)
    4. Query understanding (LLM)
    5. Symbol resolution (DB + alias map)
    6. Retrieval (deterministic)
    7. Response generation (LLM)

    Args:
        db: AsyncSession for database queries
        user_id: User ID for ownership validation
        session_id: Chat session ID
        query: User query text

    Returns:
        RAGResponse with answer and sources
    """
    settings = get_settings()

    # Step 1: Validate session ownership
    session_result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id,
        )
    )
    session = session_result.scalar_one_or_none()

    if not session:
        logger.warning(f"Session not found or access denied: session_id={session_id}, user_id={user_id}")
        return RAGResponse(
            answer_text="Oturum bulunamadı. Lütfen yeni bir oturum başlatın.",
            sources=[],
            stock_symbol=None,
            document_type=DocumentType.ANY,
            insufficient_context=True,
        )

    # Step 2: Get memory context
    memory_messages = await get_last_messages(
        db=db,
        session_id=session_id,
        limit=settings.chat_memory_window,
    )
    memory_context = format_memory_context(memory_messages)
    logger.debug(f"Memory context: {len(memory_messages)} messages")

    # Create shared HTTP client for LLM calls
    async with httpx.AsyncClient(timeout=settings.llm_timeout) as http_client:

        # Step 3: Quick greeting check (rule-based, no LLM)
        if is_greeting(query):
            logger.debug("Greeting detected (rule-based)")
            return RAGResponse(
                answer_text=GREETING_RESPONSE,
                sources=[],
                stock_symbol=None,
                document_type=DocumentType.ANY,
                confidence_note="Sistem belge odaklı çalışmaktadır.",
                insufficient_context=False,
            )

        # Step 4: Query understanding
        understanding = await analyze_query(
            query=query,
            http_client=http_client,
        )
        logger.debug(f"Query understanding: intent={understanding.intent}, symbol={understanding.candidate_symbol}")

        # Step 5: Symbol resolution
        resolved_symbol = await resolve_symbol(
            db=db,
            candidate_symbol=understanding.candidate_symbol,
        )
        logger.debug(f"Resolved symbol: {resolved_symbol}")

        # Step 6: Retrieval
        retrieval = await run_retrieval(
            query=query,
            resolved_symbol=resolved_symbol,
            document_type=understanding.document_type,
            understanding=understanding,
        )
        retrieval = await enrich_retrieval_sources(db, retrieval)
        logger.debug(f"Retrieval: {len(retrieval.chunks)} chunks, sufficient={retrieval.has_sufficient_context}")

        # Step 7: Response generation
        response = await generate_response(
            original_query=query,  # Use original, not normalized
            understanding=understanding,
            retrieval=retrieval,
            memory_context=memory_context,
            http_client=http_client,
        )

        # Override stock_symbol with resolved symbol
        response.stock_symbol = resolved_symbol

        return response


async def create_chat_session(
    db: AsyncSession,
    user_id: int,
    title: str | None = None,
) -> ChatSession:
    """Create a new chat session.

    Args:
        db: AsyncSession for database queries
        user_id: User ID
        title: Optional session title

    Returns:
        Created ChatSession object
    """
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
    """Get all chat sessions for a user.

    Args:
        db: AsyncSession for database queries
        user_id: User ID

    Returns:
        List of ChatSession objects (newest first)
    """
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
    """Save a chat message to the database.

    Args:
        db: AsyncSession for database queries
        session_id: Chat session ID
        role: Message role ("user" or "assistant")
        content: Message content
        sources_metadata: Optional list of source references

    Returns:
        Created ChatMessage object
    """
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
