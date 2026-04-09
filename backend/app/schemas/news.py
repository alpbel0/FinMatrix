"""News request/response schemas."""

from datetime import datetime

from pydantic import BaseModel


class NewsResponse(BaseModel):
    """Single news item response."""

    id: int
    stock_id: int | None = None
    symbol: str | None = None  # Resolved from stock relationship
    title: str
    category: str | None = None  # Derived: "financial", "activity", "kap"
    filing_type: str | None = None  # Raw: "FR", "FAR"
    excerpt: str | None = None
    source_url: str | None = None
    source_type: str | None = None  # "kap", "manual"
    is_read: bool = False  # User-specific read status
    created_at: datetime


class NewsListResponse(BaseModel):
    """Response for news feed endpoint."""

    items: list[NewsResponse]
    total: int
    unread_count: int


class NewsReadRequest(BaseModel):
    """Request to mark news as read/unread."""

    is_read: bool = True