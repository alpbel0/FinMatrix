"""
KAP Report model for company disclosure reports from kap.org.tr.

This module contains:
- KAPReport: KAP disclosure reports with PDF sync status
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base
from app.models.enums import SyncStatus

if TYPE_CHECKING:
    from app.models.document_chunk import DocumentChunk
    from app.models.stock import Stock


class KAPReport(Base):
    """
    KAP disclosure reports from kap.org.tr.

    Stores company disclosure information including PDF URL,
    publication date, and ChromaDB sync status for RAG pipeline.
    """

    __tablename__ = "kap_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    stock_id: Mapped[int] = mapped_column(
        ForeignKey("stocks.id", ondelete="CASCADE"),
        nullable=False,
    )
    bildirim_no: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    pdf_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    published_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    fetched_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    chroma_sync_status: Mapped[SyncStatus] = mapped_column(
        Enum(SyncStatus, name="sync_status_enum", create_type=False),
        default=SyncStatus.PENDING,
        nullable=False,
    )
    chunk_count: Mapped[int] = mapped_column(default=0, nullable=False)

    # Relationship to Stock
    stock: Mapped["Stock"] = relationship(back_populates="kap_reports")

    # One-to-many relationship with DocumentChunk
    document_chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="kap_report", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_kap_reports_stock", "stock_id"),
        Index("idx_kap_reports_published", "published_date"),
    )

    def __repr__(self) -> str:
        return f"<KAPReport(id={self.id}, bildirim_no='{self.bildirim_no}', title='{self.title[:30]}...')>"