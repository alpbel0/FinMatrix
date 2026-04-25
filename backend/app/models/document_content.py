from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DocumentContent(Base):
    __tablename__ = "document_contents"
    __table_args__ = (
        UniqueConstraint("stock_id", "content_hash", name="uq_document_content_stock_hash"),
        Index("idx_document_contents_stock_created", "stock_id", "created_at"),
        Index("idx_document_contents_parent_id", "parent_content_id"),
        Index("idx_document_contents_synthetic", "is_synthetic_section"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    content_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    processed_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_type: Mapped[str] = mapped_column(String(50), nullable=False, default="paragraph")
    content_origin: Mapped[str] = mapped_column(String(50), nullable=False, default="pdf_docling")
    section_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_synthetic_section: Mapped[bool] = mapped_column(default=False, nullable=False)
    parser_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    report_occurrence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    first_seen_report_id: Mapped[int | None] = mapped_column(ForeignKey("kap_reports.id", ondelete="SET NULL"), nullable=True)
    last_seen_report_id: Mapped[int | None] = mapped_column(ForeignKey("kap_reports.id", ondelete="SET NULL"), nullable=True)
    parent_content_id: Mapped[int | None] = mapped_column(
        ForeignKey("document_contents.id", ondelete="CASCADE"),
        nullable=True,
    )
    embedding_status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING")
    chroma_document_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
