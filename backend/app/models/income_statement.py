"""
Income statement model for company profitability data.

This module contains:
- IncomeStatement: Company income statement (revenue, profit, margins)
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


class IncomeStatement(Base):
    """
    Company income statement data.

    Stores profitability data including revenue, net income,
    operating income, gross profit, and EBITDA.
    Data is sourced from yfinance and KAP filings.
    """

    __tablename__ = "income_statements"

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

    # Income statement items (all in TL)
    revenue: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 2), nullable=True)
    net_income: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 2), nullable=True)
    operating_income: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(20, 2), nullable=True
    )
    gross_profit: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(20, 2), nullable=True
    )
    ebitda: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 2), nullable=True)

    # Relationship to Stock
    stock: Mapped["Stock"] = relationship(back_populates="income_statements")

    __table_args__ = (
        UniqueConstraint(
            "stock_id", "period", "date", name="uq_income_statement"
        ),
        Index("idx_income_statements_stock", "stock_id"),
        Index("idx_income_statements_date", "date"),
    )

    def __repr__(self) -> str:
        return f"<IncomeStatement(stock_id={self.stock_id}, period={self.period.value}, date='{self.date}')>"