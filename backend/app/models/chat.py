"""Chat models for SQLAlchemy ORM.

This module defines the database models for chat sessions and messages.

Models:
- ChatSession: Represents a chat conversation session
- ChatMessage: Represents a single message in a session
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ChatSession(Base):
    """Chat session model.

    Represents a conversation session between a user and the AI.

    Attributes:
        id: Primary key
        user_id: Foreign key to users table
        title: Optional session title
        created_at: Session creation timestamp
    """

    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ChatMessage(Base):
    """Chat message model.

    Represents a single message in a chat session.

    Attributes:
        id: Primary key
        session_id: Foreign key to chat_sessions table
        role: Message role ("user" or "assistant")
        content: Message text content
        sources_metadata: JSONB array of source references for assistant messages
        created_at: Message creation timestamp
    """

    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # "user" | "assistant"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sources_metadata: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list
    )
    # Note: MutableList not used for now; if change tracking needed later, consider it.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )