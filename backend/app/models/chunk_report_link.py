from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ChunkReportLink(Base):
    __tablename__ = "chunk_report_links"
    __table_args__ = (
        UniqueConstraint("content_id", "kap_report_id", "element_order", name="uq_chunk_report_link_content_report_order"),
        Index("idx_chunk_report_links_stock_published", "stock_id", "published_at"),
        Index("idx_chunk_report_links_stock_filing_published", "stock_id", "filing_type", "published_at"),
        Index("idx_chunk_report_links_content_id", "content_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    content_id: Mapped[int] = mapped_column(ForeignKey("document_contents.id", ondelete="CASCADE"), nullable=False)
    kap_report_id: Mapped[int] = mapped_column(ForeignKey("kap_reports.id", ondelete="CASCADE"), nullable=False)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False)
    filing_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    report_section: Mapped[str | None] = mapped_column(String(500), nullable=True)
    element_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_summary_prefix: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    content_origin: Mapped[str] = mapped_column(String(50), nullable=False, default="pdf_docling")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
