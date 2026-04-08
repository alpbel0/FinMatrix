from datetime import date

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