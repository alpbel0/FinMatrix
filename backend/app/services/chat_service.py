"""Chat service for session and message management.

This service handles:
- Session CRUD operations
- Message persistence
- RAG pipeline integration

Separates concerns from chat_rag_service (which handles the RAG pipeline).
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.chat import ChatMessage, ChatSession
from app.schemas.chat import RAGResponse, SessionCreateRequest, SessionResponse
from app.services.chat_rag_service import process_chat_query, save_message
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
    # Save user message
    await save_message(
        db=db,
        session_id=session_id,
        role="user",
        content=message,
    )

    # Process through RAG pipeline
    response = await process_chat_query(
        db=db,
        user_id=user_id,
        session_id=session_id,
        query=message,
    )

    # Save assistant message with sources
    sources_metadata = [s.model_dump() for s in response.sources]
    await save_message(
        db=db,
        session_id=session_id,
        role="assistant",
        content=response.answer_text,
        sources_metadata=sources_metadata,
    )

    return response


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