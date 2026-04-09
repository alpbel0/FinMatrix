"""Watchlist request/response schemas."""

from datetime import date, datetime

from pydantic import BaseModel


class WatchlistAddRequest(BaseModel):
    """Request to add a stock to watchlist."""

    symbol: str
    notifications_enabled: bool = True


class WatchlistItemResponse(BaseModel):
    """Single watchlist item with stock info and price snapshot."""

    id: int
    symbol: str
    company_name: str | None = None
    sector: str | None = None
    notifications_enabled: bool
    latest_price: float | None = None
    price_change: float | None = None  # Absolute price change
    price_change_percent: float | None = None  # Percentage change
    price_date: date | None = None  # Date of latest price
    created_at: datetime


class WatchlistListResponse(BaseModel):
    """Response for watchlist list endpoint."""

    items: list[WatchlistItemResponse]
    total: int


class NotificationToggleRequest(BaseModel):
    """Request to toggle notifications for a watchlist item."""

    notifications_enabled: bool