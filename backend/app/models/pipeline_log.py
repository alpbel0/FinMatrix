"""
Pipeline log model for data pipeline execution tracking.

This module contains:
- PipelineLog: Execution logs for data sync jobs
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional
import uuid

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base
from app.models.enums import PipelineStatus

if TYPE_CHECKING:
    from app.models.eval_log import EvalLog
    from app.models.stock import Stock


class PipelineLog(Base):
    """Pipeline execution log for data sync jobs."""

    __tablename__ = "pipeline_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4
    )
    pipeline_name: Mapped[str] = mapped_column(String(100), nullable=False)
    job_name: Mapped[str] = mapped_column(String(100), nullable=False)
    step_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    stock_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("stocks.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[PipelineStatus] = mapped_column(
        Enum(PipelineStatus, name="pipeline_status_enum", create_type=False),
        default=PipelineStatus.PENDING,
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    processed_count: Mapped[int] = mapped_column(default=0, nullable=False)
    details: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Relationships
    stock: Mapped[Optional["Stock"]] = relationship(back_populates="pipeline_logs")
    eval_logs: Mapped[list["EvalLog"]] = relationship(back_populates="pipeline_log")

    __table_args__ = (
        Index("idx_pipeline_logs_run_id", "run_id"),
        Index("idx_pipeline_logs_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<PipelineLog(id={self.id}, run_id={self.run_id}, status={self.status})>"