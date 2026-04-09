"""Scheduler API schemas for admin endpoints."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class FinancialReportingModeRequest(BaseModel):
    """Request to enable/disable financial reporting mode."""

    enabled: bool


class FinancialReportingModeResponse(BaseModel):
    """Response for financial reporting mode status."""

    financial_reporting_mode: bool
    financial_reporting_until: datetime | None


class ManualSyncRequest(BaseModel):
    """Request to trigger a manual sync."""

    universe: str = "all"  # "all", "bist100", "watchlist"


class ManualSyncResponse(BaseModel):
    """Response for manual sync trigger."""

    run_id: str
    status: str
    symbols_count: int
    message: str | None = None


class JobStatus(BaseModel):
    """Status of a scheduled job."""

    last_run: datetime | None
    last_status: str | None
    next_run: datetime | None


class SchedulerStatusResponse(BaseModel):
    """Full scheduler status response."""

    is_running: bool
    financial_reporting_mode: bool
    financial_reporting_until: datetime | None
    jobs: dict[str, JobStatus]