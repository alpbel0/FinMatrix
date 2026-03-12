"""
Watchlist model for user stock tracking.

This module contains:
- Watchlist: Many-to-many relationship between users and stocks they follow
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base

if TYPE_CHECKING:
    from app.models.stock import Stock
    from app.models.user import User


class Watchlist(Base):
    """
    User's watchlist - tracks stocks they follow.

    Composite primary key (user_id, stock_id) ensures a user can only
    add a stock to their watchlist once.
    """

    __tablename__ = "watchlist"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    stock_id: Mapped[int] = mapped_column(
        ForeignKey("stocks.id", ondelete="CASCADE"),
        primary_key=True,
    )
    added_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )
    notification_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="watchlist_entries")
    stock: Mapped["Stock"] = relationship(back_populates="watchlist_entries")

    __table_args__ = (Index("idx_watchlist_user", "user_id"),)

    def __repr__(self) -> str:
        return f"<Watchlist(user_id={self.user_id}, stock_id={self.stock_id})>"