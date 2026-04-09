"""Chat trace model for debugging RAG pipeline execution."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ChatTrace(Base):
    """Structured trace for one chat pipeline execution."""

    __tablename__ = "chat_traces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    user_message_id: Mapped[int | None] = mapped_column(
        ForeignKey("chat_messages.id", ondelete="SET NULL"), nullable=True
    )
    assistant_message_id: Mapped[int | None] = mapped_column(
        ForeignKey("chat_messages.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="STARTED")
    original_query: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_query: Mapped[str | None] = mapped_column(Text, nullable=True)
    candidate_symbol: Mapped[str | None] = mapped_column(String(20), nullable=True)
    resolved_symbol: Mapped[str | None] = mapped_column(String(20), nullable=True)
    document_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    intent: Mapped[str | None] = mapped_column(String(30), nullable=True)
    query_understanding_model: Mapped[str | None] = mapped_column(String(200), nullable=True)
    response_model: Mapped[str | None] = mapped_column(String(200), nullable=True)
    memory_context_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    retrieved_chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    retrieval_confidence: Mapped[float | None] = mapped_column(nullable=True)
    context_total_chars: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    has_sufficient_context: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sources_metadata: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    understanding_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    retrieval_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    response_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
