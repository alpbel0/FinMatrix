"""
Eval log model for AI response evaluation metrics.

This module contains:
- EvalLog: AI response quality metrics and hallucination detection
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base

if TYPE_CHECKING:
    from app.models.chat import ChatMessage
    from app.models.pipeline_log import PipelineLog


class EvalLog(Base):
    """AI response evaluation metrics."""

    __tablename__ = "eval_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    message_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("chat_messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    pipeline_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pipeline_logs.run_id", ondelete="SET NULL"),
        nullable=True,
    )
    bert_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 4), nullable=True)
    rouge_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 4), nullable=True)
    retrieval_score: Mapped[Optional[float]] = mapped_column(
        Numeric(5, 4), nullable=True
    )
    judge_model_used: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    judge_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_hallucinated: Mapped[bool] = mapped_column(default=False, nullable=False)
    retry_count: Mapped[int] = mapped_column(default=0, nullable=False)
    source_chunks_used: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    details: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )

    # Relationships
    message: Mapped[Optional["ChatMessage"]] = relationship(back_populates="eval_logs")
    pipeline_log: Mapped[Optional["PipelineLog"]] = relationship(
        back_populates="eval_logs"
    )

    __table_args__ = (
        Index("idx_eval_hallucinated", "is_hallucinated", "pipeline_run_id"),
        Index("idx_eval_logs_message", "message_id"),
    )

    def __repr__(self) -> str:
        return f"<EvalLog(id={self.id}, is_hallucinated={self.is_hallucinated})>"