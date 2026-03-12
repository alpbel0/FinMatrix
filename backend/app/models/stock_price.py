"""
Stock price model for daily price data.

This module contains:
- StockPrice: Daily OHLCV data partitioned by month
"""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.stock import Stock


class StockPrice(Base):
    """
    Daily stock price data (partitioned by month).

    Stores OHLCV (Open, High, Low, Close, Volume) data for each stock.
    Uses PostgreSQL table partitioning by timestamp for performance
    on large historical datasets.

    The table is partitioned by RANGE on the timestamp column.
    Partitions are created monthly via the create_partitions.py script.
    """

    __tablename__ = "stock_prices"

    stock_id: Mapped[int] = mapped_column(
        ForeignKey("stocks.id", ondelete="CASCADE"),
        primary_key=True,
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        primary_key=True,
    )
    open: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Relationship to Stock
    stock: Mapped["Stock"] = relationship(back_populates="prices")

    __table_args__ = (
        Index("idx_stock_prices_stock_time", "stock_id", "timestamp"),
        {"postgresql_partition_by": "RANGE (timestamp)"},
    )

    def __repr__(self) -> str:
        return f"<StockPrice(stock_id={self.stock_id}, timestamp='{self.timestamp}', close={self.close})>"