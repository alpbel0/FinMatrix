"""Chat router - handles AI chat sessions and messages."""

from fastapi import APIRouter

router = APIRouter()


# TODO: Implement endpoints in later tasks
# POST /sessions - Create new chat session
# GET /sessions - List user's sessions
# GET /sessions/{id} - Get session with messages
# DELETE /sessions/{id} - Delete session
# POST /sessions/{id}/messages - Send message (sync)
# POST /sessions/{id}/messages/stream - Send message (SSE stream)