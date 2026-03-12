"""
News models for news items and user read status.

This module contains:
- News: News items from various sources (KAP summary, external, manual)
- UserNews: User-news relationship for read status tracking
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import NewsSource

if TYPE_CHECKING:
    from app.models.kap_report import KAPReport
    from app.models.stock import Stock
    from app.models.user import User


class News(Base):
    """
    News items from various sources.

    Stores news content with source tracking. Can be linked to a specific
    stock or be general market news (stock_id is nullable).
    """

    __tablename__ = "news"

    id: Mapped[int] = mapped_column(primary_key=True)
    stock_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("stocks.id", ondelete="SET NULL"),
        nullable=True,  # Nullable for general market news
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    published_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    source_type: Mapped[NewsSource] = mapped_column(
        Enum(NewsSource, name="news_source_enum", create_type=False),
        nullable=False,
    )
    source_ref_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("kap_reports.id", ondelete="SET NULL"),
        nullable=True,  # References kap_reports.id when source_type is kap_summary
    )

    # Relationship to Stock (optional)
    stock: Mapped[Optional["Stock"]] = relationship(back_populates="news_items")
    # Relationship to KAPReport (optional, for kap_summary source)
    kap_report: Mapped[Optional["KAPReport"]] = relationship(
        foreign_keys=[source_ref_id]
    )

    __table_args__ = (
        Index("idx_news_stock", "stock_id"),
        Index("idx_news_published", "published_date"),
        Index("idx_news_source_type", "source_type"),
    )

    def __repr__(self) -> str:
        return f"<News(id={self.id}, title='{self.title[:30]}...', source={self.source_type})>"


class UserNews(Base):
    """
    User-news relationship for read status tracking.

    Composite primary key on (user_id, news_id) ensures one read status
    per user per news item.
    """

    __tablename__ = "user_news"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    news_id: Mapped[int] = mapped_column(
        ForeignKey("news.id", ondelete="CASCADE"),
        primary_key=True,
    )
    is_read: Mapped[bool] = mapped_column(default=False, nullable=False)
    read_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="news_read_status")
    news: Mapped["News"] = relationship()

    __table_args__ = (Index("idx_user_news_user", "user_id"),)

    def __repr__(self) -> str:
        return f"<UserNews(user_id={self.user_id}, news_id={self.news_id}, is_read={self.is_read})>"