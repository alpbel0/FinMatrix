"""
Balance sheet model for company financial position data.

This module contains:
- BalanceSheet: Company balance sheet (assets, liabilities, equity)
"""

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Date, Enum, ForeignKey, Index, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import PeriodType

if TYPE_CHECKING:
    from app.models.stock import Stock


class BalanceSheet(Base):
    """
    Company balance sheet data.

    Stores financial position data including assets, liabilities,
    and equity. Data is sourced from yfinance and KAP filings.
    """

    __tablename__ = "balance_sheets"

    id: Mapped[int] = mapped_column(primary_key=True)
    stock_id: Mapped[int] = mapped_column(
        ForeignKey("stocks.id", ondelete="CASCADE"),
        nullable=False,
    )
    period: Mapped[PeriodType] = mapped_column(
        Enum(PeriodType, name="period_type_enum", create_type=False),
        nullable=False,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    fiscal_year: Mapped[int] = mapped_column(nullable=False)
    fiscal_quarter: Mapped[Optional[int]] = mapped_column(nullable=True)

    # Balance sheet items (all in TL)
    total_assets: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(20, 2), nullable=True
    )
    total_liabilities: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(20, 2), nullable=True
    )
    equity: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 2), nullable=True)
    cash: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 2), nullable=True)
    total_debt: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 2), nullable=True)

    # Relationship to Stock
    stock: Mapped["Stock"] = relationship(back_populates="balance_sheets")

    __table_args__ = (
        UniqueConstraint(
            "stock_id", "period", "date", name="uq_balance_sheet"
        ),
        Index("idx_balance_sheets_stock", "stock_id"),
        Index("idx_balance_sheets_date", "date"),
    )

    def __repr__(self) -> str:
        return f"<BalanceSheet(stock_id={self.stock_id}, period={self.period.value}, date='{self.date}')>"