"""
User and TelegramSettings models for authentication and notifications.

This module contains:
- User: Core user account model with authentication fields
- TelegramSettings: User's Telegram notification preferences (one-to-one)
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base

if TYPE_CHECKING:
    from app.models.news import UserNews
    from app.models.watchlist import Watchlist


class User(Base):
    """
    User account model for authentication and profile management.

    Stores core user information including credentials, Telegram integration,
    and notification preferences.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    telegram_chat_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    notification_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # One-to-one relationship with TelegramSettings
    telegram_settings: Mapped[Optional["TelegramSettings"]] = relationship(
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    # One-to-many relationship with Watchlist
    watchlist_entries: Mapped[list["Watchlist"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    # One-to-many relationship with UserNews (read status)
    news_read_status: Mapped[list["UserNews"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("idx_users_email", "email"),)

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}', email='{self.email}')>"


class TelegramSettings(Base):
    """
    Telegram notification settings for a user.

    Stores notification timing and event type preferences as JSONB.
    Each user has at most one TelegramSettings record (one-to-one).
    """

    __tablename__ = "telegram_settings"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    notification_times: Mapped[dict] = mapped_column(
        JSONB, default=dict, nullable=False
    )
    event_types: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Relationship back to User
    user: Mapped["User"] = relationship(back_populates="telegram_settings")

    def __repr__(self) -> str:
        return f"<TelegramSettings(user_id={self.user_id})>"