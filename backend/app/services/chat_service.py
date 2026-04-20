"""Chat service for session and message management."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.chat import ChatMessage, ChatSession
from app.schemas.chat import RAGResponse, SessionCreateRequest, SessionResponse
from app.services.chat_rag_service import run_chat_pipeline, save_message
from app.services.chat_trace_service import (
    create_chat_trace,
    finalize_chat_trace_failure,
    finalize_chat_trace_success,
)
from app.services.utils.logging import logger


# ============================================================================
# Session Management
# ============================================================================


async def create_session(
    db: AsyncSession,
    user_id: int,
    request: SessionCreateRequest,
) -> SessionResponse:
    """Create a new chat session.

    Args:
        db: AsyncSession for database queries
        user_id: User ID
        request: Session creation request

    Returns:
        SessionResponse with created session details
    """
    session = ChatSession(
        user_id=user_id,
        title=request.title,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    return SessionResponse(
        id=session.id,
        title=session.title,
        created_at=session.created_at,
    )


async def list_sessions(
    db: AsyncSession,
    user_id: int,
) -> list[SessionResponse]:
    """List all chat sessions for a user.

    Args:
        db: AsyncSession for database queries
        user_id: User ID

    Returns:
        List of SessionResponse objects
    """
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == user_id)
        .order_by(ChatSession.created_at.desc())
    )
    sessions = result.scalars().all()

    return [
        SessionResponse(
            id=s.id,
            title=s.title,
            created_at=s.created_at,
        )
        for s in sessions
    ]


async def get_session(
    db: AsyncSession,
    session_id: int,
    user_id: int,
) -> ChatSession | None:
    """Get a chat session by ID with ownership check.

    Args:
        db: AsyncSession for database queries
        session_id: Session ID
        user_id: User ID for ownership check

    Returns:
        ChatSession or None if not found or not owned
    """
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


# ============================================================================
# Message Management
# ============================================================================


async def send_message(
    db: AsyncSession,
    user_id: int,
    session_id: int,
    message: str,
) -> RAGResponse:
    """Send a message and get RAG response.

    This is the main entry point for the chat API.

    Args:
        db: AsyncSession for database queries
        user_id: User ID
        session_id: Session ID
        message: User message

    Returns:
        RAGResponse with answer and sources
    """
    started_at = datetime.now(timezone.utc)

    user_message = await save_message(
        db=db,
        session_id=session_id,
        role="user",
        content=message,
    )
    trace = await create_chat_trace(
        db=db,
        session_id=session_id,
        user_id=user_id,
        user_message_id=user_message.id,
        original_query=message,
    )

    pipeline_result = None
    try:
        pipeline_result = await run_chat_pipeline(
            db=db,
            user_id=user_id,
            session_id=session_id,
            query=message,
        )
        response = pipeline_result.response
        if response is None:
            raise RuntimeError("Chat pipeline returned no response")

        assistant_message = await save_message(
            db=db,
            session_id=session_id,
            role="assistant",
            content=response.answer_text,
            sources_metadata=[s.model_dump(mode="json") for s in response.sources],
        )

        await finalize_chat_trace_success(
            db=db,
            trace=trace,
            pipeline_result=pipeline_result,
            assistant_message_id=assistant_message.id,
            duration_ms=int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000),
        )
        return response
    except Exception as exc:
        await db.rollback()
        await finalize_chat_trace_failure(
            db=db,
            trace=trace,
            error_message=str(exc),
            duration_ms=int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000),
            pipeline_result=pipeline_result,
        )
        logger.error("Chat send_message error: %s", exc)
        raise


async def get_session_messages(
    db: AsyncSession,
    session_id: int,
    limit: int = 50,
) -> list[ChatMessage]:
    """Get messages for a session.

    Args:
        db: AsyncSession for database queries
        session_id: Session ID
        limit: Maximum number of messages

    Returns:
        List of ChatMessage objects
    """
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
        .limit(limit)
    )
    return list(result.scalars().all())
