"""Admin triage view API schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CacheDecisionItem(BaseModel):
    """A single processing_cache decision entry."""

    section_path: str
    decision: str
    suggested_label: str | None = None
    decided_by: str
    decided_at: datetime


class SyntheticContentItem(BaseModel):
    """A single synthetic document_content entry."""

    id: int
    section_path: str | None = None
    content_preview: str
    stock_symbol: str | None = None
    element_type: str
    created_at: datetime
    is_synthetic_section: bool = True


class TriageStats(BaseModel):
    """Aggregated triage statistics."""

    total_cache_entries: int
    keep_count: int
    discard_count: int
    synthetic_count: int


class TriageViewResponse(BaseModel):
    """Response for the admin triage view endpoint."""

    cache_decisions: list[CacheDecisionItem]
    synthetic_contents: list[SyntheticContentItem]
    stats: TriageStats


class TriageViewQueryParams(BaseModel):
    """Query parameters for the admin triage view endpoint."""

    decision: str | None = None
    search: str | None = None
    synthetic_only: bool = False
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
