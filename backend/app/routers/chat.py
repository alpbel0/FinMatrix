"""Chat API router.

Endpoints:
- GET /api/chat/sessions - List user's chat sessions
- POST /api/chat/sessions - Create new session
- GET /api/chat/sessions/{id}/messages - Get session messages
- POST /api/chat/messages - Send message and get RAG response
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session
from app.schemas.chat import (
    MessageRequest,
    RAGResponse,
    SessionCreateRequest,
    SessionResponse,
)
from app.services.auth_service import get_current_user
from app.services.chat_service import (
    create_session,
    get_session,
    get_session_messages,
    list_sessions,
    send_message,
)
from app.services.utils.logging import logger

router = APIRouter(prefix="/api/chat", tags=["chat"])
security = HTTPBearer()


# ============================================================================
# Session Endpoints
# ============================================================================


@router.get("/sessions", response_model=list[SessionResponse])
async def list_user_sessions(
    db: AsyncSession = Depends(get_db_session),
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> list[SessionResponse]:
    """List all chat sessions for the current user."""
    user = await get_current_user(db, credentials.credentials)
    return await list_sessions(db, user.id)


@router.post("/sessions", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_new_session(
    request: SessionCreateRequest,
    db: AsyncSession = Depends(get_db_session),
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> SessionResponse:
    """Create a new chat session."""
    user = await get_current_user(db, credentials.credentials)
    return await create_session(db, user.id, request)


@router.get("/sessions/{session_id}/messages")
async def get_messages(
    session_id: int,
    db: AsyncSession = Depends(get_db_session),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Get messages for a specific session."""
    user = await get_current_user(db, credentials.credentials)

    # Verify session ownership
    session = await get_session(db, session_id, user.id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    messages = await get_session_messages(db, session_id)
    return {
        "session_id": session_id,
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "sources": m.sources_metadata,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ],
    }


# ============================================================================
# Message Endpoint
# ============================================================================


@router.post("/messages", response_model=RAGResponse)
async def send_chat_message(
    request: MessageRequest,
    db: AsyncSession = Depends(get_db_session),
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> RAGResponse:
    """Send a message and get RAG response.

    This is the main chat endpoint that processes user queries
    through the RAG pipeline.
    """
    user = await get_current_user(db, credentials.credentials)

    # Verify session ownership
    session = await get_session(db, request.session_id, user.id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    try:
        response = await send_message(
            db=db,
            user_id=user.id,
            session_id=request.session_id,
            message=request.message,
        )
        return response
    except Exception as e:
        logger.error(f"Chat message error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process message",
        )