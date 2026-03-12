"""
Document chunk model for RAG pipeline.

This module contains:
- DocumentChunk: PDF chunks from KAP reports for embedding
"""

from typing import TYPE_CHECKING, Optional

from sqlalchemy import Enum, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import EmbeddingStatus

if TYPE_CHECKING:
    from app.models.kap_report import KAPReport


class DocumentChunk(Base):
    """Document chunk from KAP report for RAG pipeline."""

    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    kap_report_id: Mapped[int] = mapped_column(
        ForeignKey("kap_reports.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(nullable=False)
    chunk_text_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    chroma_document_id: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    embedding_status: Mapped[EmbeddingStatus] = mapped_column(
        Enum(EmbeddingStatus, name="embedding_status_enum", create_type=False),
        default=EmbeddingStatus.PENDING,
        nullable=False,
    )

    # Relationship
    kap_report: Mapped["KAPReport"] = relationship(back_populates="document_chunks")

    __table_args__ = (
        Index("idx_document_chunks_report", "kap_report_id"),
        UniqueConstraint(
            "kap_report_id", "chunk_index", name="uq_document_chunks_report_index"
        ),
    )

    def __repr__(self) -> str:
        return f"<DocumentChunk(id={self.id}, kap_report_id={self.kap_report_id}, chunk_index={self.chunk_index})>"