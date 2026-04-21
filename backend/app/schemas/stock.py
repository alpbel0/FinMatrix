from datetime import date, datetime

from pydantic import BaseModel


class StockResponse(BaseModel):
    """Basic stock info for list items."""
    symbol: str
    company_name: str | None = None
    sector: str | None = None


class StockDetailResponse(BaseModel):
    """Full stock details for single stock endpoint."""
    symbol: str
    company_name: str | None = None
    sector: str | None = None
    exchange: str
    is_active: bool


class StockListResponse(BaseModel):
    """Response for stock list endpoint with pagination info."""
    stocks: list[StockResponse]
    total: int


class PriceBarResponse(BaseModel):
    """Single price bar (OHLCV) for price history."""
    date: date
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: float | None = None


class PriceHistoryResponse(BaseModel):
    """Response for price history endpoint."""
    symbol: str
    prices: list[PriceBarResponse]
    count: int


class StockSnapshotResponse(BaseModel):
    """Latest stored snapshot for a stock."""

    symbol: str
    snapshot_date: date | None = None
    fetched_at: datetime | None = None
    source: str | None = None
    field_sources: dict[str, str] | None = None
    is_partial: bool = True
    completeness_score: float = 0.0
    missing_fields_count: int = 0
    is_stale: bool = True
    stale_reason: str | None = None
    last_successful_sync_at: datetime | None = None
    pe_ratio: float | None = None
    pb_ratio: float | None = None
    dividend_yield: float | None = None
    trailing_eps: float | None = None
    roe: float | None = None
    roa: float | None = None
    current_ratio: float | None = None
    debt_equity: float | None = None
    revenue_growth: float | None = None
    net_profit_growth: float | None = None
    foreign_ratio: float | None = None
    free_float: float | None = None
    year_high: float | None = None
    year_low: float | None = None
    ma_50: float | None = None
    ma_200: float | None = None
    market_cap: float | None = None
    last_price: float | None = None
    daily_volume: float | None = None


class HistoricalStockSnapshotPointResponse(BaseModel):
    """Single historical snapshot point."""

    snapshot_date: date
    source: str | None = None
    field_sources: dict[str, str] | None = None
    is_partial: bool = True
    completeness_score: float = 0.0
    pe_ratio: float | None = None
    pb_ratio: float | None = None
    dividend_yield: float | None = None
    trailing_eps: float | None = None
    roe: float | None = None
    roa: float | None = None
    current_ratio: float | None = None
    debt_equity: float | None = None
    revenue_growth: float | None = None
    net_profit_growth: float | None = None
    foreign_ratio: float | None = None
    free_float: float | None = None
    year_high: float | None = None
    year_low: float | None = None
    ma_50: float | None = None
    ma_200: float | None = None
    market_cap: float | None = None
    last_price: float | None = None
    daily_volume: float | None = None


class HistoricalStockSnapshotResponse(BaseModel):
    """Historical snapshots for a stock."""

    symbol: str
    snapshots: list[HistoricalStockSnapshotPointResponse]
    count: int
