from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class StockSnapshotRecord(Base):
    __tablename__ = "stock_snapshots"
    __table_args__ = (
        Index("idx_stock_snapshots_stock_date", "stock_id", "snapshot_date"),
        Index("idx_stock_snapshots_snapshot_date", "snapshot_date"),
    )

    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id", ondelete="CASCADE"), primary_key=True)
    snapshot_date: Mapped[date] = mapped_column(Date, primary_key=True)

    pe_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    pb_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    dividend_yield: Mapped[float | None] = mapped_column(Float, nullable=True)
    trailing_eps: Mapped[float | None] = mapped_column(Float, nullable=True)
    roe: Mapped[float | None] = mapped_column(Float, nullable=True)
    roa: Mapped[float | None] = mapped_column(Float, nullable=True)
    current_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    debt_equity: Mapped[float | None] = mapped_column(Float, nullable=True)
    revenue_growth: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_profit_growth: Mapped[float | None] = mapped_column(Float, nullable=True)
    foreign_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    free_float: Mapped[float | None] = mapped_column(Float, nullable=True)
    year_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    year_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    ma_50: Mapped[float | None] = mapped_column(Float, nullable=True)
    ma_200: Mapped[float | None] = mapped_column(Float, nullable=True)
    market_cap: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    daily_volume: Mapped[float | None] = mapped_column(Float, nullable=True)

    source: Mapped[str] = mapped_column(String(100), nullable=False, default="borsapy")
    field_sources: Mapped[dict[str, str] | None] = mapped_column(JSONB, nullable=True)
    missing_fields_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completeness_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    is_partial: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
