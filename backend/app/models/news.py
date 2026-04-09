from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class News(Base):
    __tablename__ = "news"
    __table_args__ = (UniqueConstraint("source_type", "source_id", name="uq_news_source_type_source_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stock_id: Mapped[int | None] = mapped_column(ForeignKey("stocks.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Source tracking fields for KAP -> News transformation
    source_type: Mapped[str | None] = mapped_column(String(50), nullable=True)  # "kap", "manual"
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # kap_report.id if source_type="kap"
    filing_type: Mapped[str | None] = mapped_column(String(100), nullable=True)  # Raw filing type: "FR", "FAR"
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    stock: Mapped["Stock | None"] = relationship(lazy="selectin")


class UserNews(Base):
    __tablename__ = "user_news"
    __table_args__ = (UniqueConstraint("user_id", "news_id", name="uq_user_news_user_id_news_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    news_id: Mapped[int] = mapped_column(ForeignKey("news.id", ondelete="CASCADE"), nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
