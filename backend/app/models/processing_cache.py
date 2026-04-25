from datetime import datetime

from sqlalchemy import DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ProcessingCache(Base):
    __tablename__ = "processing_cache"
    __table_args__ = (
        UniqueConstraint("section_path", name="uq_processing_cache_section_path"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    section_path: Mapped[str] = mapped_column(String(500), nullable=False)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    suggested_label: Mapped[str | None] = mapped_column(String(500), nullable=True)
    decided_by: Mapped[str] = mapped_column(String(50), nullable=False)
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
