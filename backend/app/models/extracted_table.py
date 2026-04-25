from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ExtractedTable(Base):
    __tablename__ = "extracted_tables"
    __table_args__ = (
        Index("idx_extracted_tables_kap_report_id", "kap_report_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kap_report_id: Mapped[int] = mapped_column(
        ForeignKey("kap_reports.id", ondelete="CASCADE"),
        nullable=False,
    )
    section_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    table_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    table_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
