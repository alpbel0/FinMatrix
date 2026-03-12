"""
Stock model for BIST stock master data.

This module contains:
- Stock: Core stock model with symbol, company info, and sector classification
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base

if TYPE_CHECKING:
    from app.models.watchlist import Watchlist


class Stock(Base):
    """
    BIST stock master data model.

    Stores core stock information including symbol, yfinance mapping,
    company name, sector, and active status.
    """

    __tablename__ = "stocks"

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    yfinance_symbol: Mapped[str] = mapped_column(
        String(30), unique=True, nullable=False
    )
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    sector: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    exchange: Mapped[str] = mapped_column(
        String(20), default="BIST", nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )

    # One-to-many relationship with Watchlist
    watchlist_entries: Mapped[list["Watchlist"]] = relationship(
        back_populates="stock", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("idx_stocks_symbol", "symbol"),)

    def __repr__(self) -> str:
        return f"<Stock(id={self.id}, symbol='{self.symbol}', company='{self.company_name}')>"