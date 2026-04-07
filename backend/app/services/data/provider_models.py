"""Pydantic models for provider data exchange."""

from datetime import date, datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class PeriodType(str, Enum):
    """Financial statement period type."""
    ANNUAL = "annual"
    QUARTERLY = "quarterly"


class DataSource(str, Enum):
    """Data source/provider identifier."""
    BORSAPY = "borsapy"
    # Future providers
    # YFINANCE = "yfinance"
    # MANUAL = "manual"


class ProviderCapability(str, Enum):
    """Capabilities a provider can offer."""
    PRICE_HISTORY = "price_history"
    REALTIME_QUOTE = "realtime_quote"
    FINANCIALS = "financials"
    METRICS = "metrics"
    KAP_FILINGS = "kap_filings"
    COMPANY_PROFILE = "company_profile"


# --- Core Data Models ---


class PriceBar(BaseModel):
    """Single OHLCV price bar."""
    date: date
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: float | None = None  # In lots
    adjusted_close: float | None = None  # Split/dividend adjusted close
    source: DataSource = DataSource.BORSAPY

    class Config:
        from_attributes = True


class StockSnapshot(BaseModel):
    """Current stock metrics and basic info."""
    symbol: str
    last_price: float | None = None
    change: float | None = None
    change_percent: float | None = None
    volume: float | None = None
    market_cap: float | None = Field(None, description="Market cap in TL")
    pe_ratio: float | None = Field(None, description="Price-to-Earnings ratio")
    pb_ratio: float | None = Field(None, description="Price-to-Book ratio")
    year_high: float | None = None
    year_low: float | None = None
    fifty_day_avg: float | None = None
    two_hundred_day_avg: float | None = None
    free_float: float | None = Field(None, description="Free float percentage")
    foreign_ratio: float | None = Field(None, description="Foreign ownership percentage")
    source: DataSource = DataSource.BORSAPY

    class Config:
        populate_by_name = True


class FinancialStatementRow(BaseModel):
    """Single row from a financial statement."""
    item_code: str | None = None
    item_name: str | None = None
    value: float | None = None
    period: str  # e.g., "2024Q3", "2024"
    statement_date: date


class FinancialStatementSet(BaseModel):
    """Complete financial statement data for a stock."""
    symbol: str
    period_type: PeriodType
    statement_date: date
    source: DataSource = DataSource.BORSAPY

    # Balance Sheet
    total_assets: float | None = None
    total_equity: float | None = None
    total_liabilities: float | None = None
    current_assets: float | None = None
    current_liabilities: float | None = None

    # Income Statement
    revenue: float | None = None
    gross_profit: float | None = None
    operating_income: float | None = None
    net_income: float | None = None
    ebitda: float | None = None

    # Cash Flow
    operating_cash_flow: float | None = None
    investing_cash_flow: float | None = None
    financing_cash_flow: float | None = None
    free_cash_flow: float | None = None

    # Additional rows for full statement access
    rows: list[FinancialStatementRow] | None = None

    class Config:
        from_attributes = True


class KapFiling(BaseModel):
    """KAP (Public Disclosure Platform) filing."""
    symbol: str
    title: str
    filing_type: str | None = None
    pdf_url: str | None = None
    source_url: str | None = None
    published_at: datetime | None = None
    provider: DataSource = DataSource.BORSAPY


class CompanyProfile(BaseModel):
    """Company metadata from provider."""
    symbol: str
    company_name: str | None = None
    sector: str | None = None
    industry: str | None = None
    website: str | None = None
    description: str | None = None  # longBusinessSummary equivalent
    isin: str | None = None
    exchange: str = "BIST"
    source: DataSource = DataSource.BORSAPY


class ProviderCapabilities(BaseModel):
    """Set of capabilities a provider supports."""
    supported_data: set[ProviderCapability]
    supported_markets: set[str] = Field(default_factory=lambda: {"BIST"})
    max_history_days: int = 3650  # ~10 years
    supports_intraday: bool = False
    supports_quarterly_financials: bool = True
    timeout_seconds: float = 30.0
    retry_count: int = 3

    class Config:
        # Allow set type for Pydantic v2
        arbitrary_types_allowed = True