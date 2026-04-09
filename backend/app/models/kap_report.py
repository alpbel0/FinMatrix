from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class KapReport(Base):
    __tablename__ = "kap_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stock_id: Mapped[int | None] = mapped_column(ForeignKey("stocks.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    filing_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    pdf_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sync_status: Mapped[str] = mapped_column(String(50), default="PENDING", nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Enrichment fields (from kap_sdk disclosureDetail)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    attachment_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_late: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    related_stocks: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)  # PostgreSQL JSONB array
    # PDF Download tracking fields
    local_pdf_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    pdf_download_status: Mapped[str] = mapped_column(String(50), default="PENDING", nullable=False)
    pdf_file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pdf_downloaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pdf_download_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Chunking tracking fields
    chunking_status: Mapped[str] = mapped_column(String(50), default="PENDING", nullable=False)
    chunking_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    stock: Mapped["Stock | None"] = relationship(lazy="selectin")

    __table_args__ = (
        UniqueConstraint("stock_id", "source_url", name="uq_kap_report_stock_source"),
    )
