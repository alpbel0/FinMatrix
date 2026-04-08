"""Factory helpers for creating provider models in tests.

Provides simple factory functions to create Pydantic model instances
for testing without verbose constructor calls.

Usage:
    from tests.factories import (
        create_price_bar,
        create_kap_filing,
        create_financial_statement_set,
        create_company_profile,
        create_stock_snapshot,
    )

    bar = create_price_bar(symbol="THYAO", close=250.0)
    filing = create_kap_filing(title="Financial Report")
"""

from datetime import date, datetime
from typing import Any

from app.services.data.provider_models import (
    CompanyProfile,
    DataSource,
    FinancialStatementRow,
    FinancialStatementSet,
    KapFiling,
    PeriodType,
    PriceBar,
    ProviderCapabilities,
    ProviderCapability,
    StockSnapshot,
)


# --- PriceBar Factory ---

def create_price_bar(
    date_val: date | None = None,
    open_price: float | None = 250.0,
    high: float | None = 255.0,
    low: float | None = 248.0,
    close: float | None = 252.0,
    volume: float | None = 1_000_000,
    adjusted_close: float | None = None,
    source: DataSource = DataSource.BORSAPY,
) -> PriceBar:
    """
    Create a PriceBar instance for testing.

    Args:
        date_val: Price bar date (defaults to today)
        open_price: Opening price
        high: High price
        low: Low price
        close: Closing price
        volume: Trading volume
        adjusted_close: Adjusted close price (defaults to close)
        source: Data source

    Returns:
        PriceBar instance
    """
    return PriceBar(
        date=date_val or date.today(),
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=volume,
        adjusted_close=adjusted_close if adjusted_close is not None else close,
        source=source,
    )


def create_price_bar_with_nan(
    date_val: date | None = None,
    nan_fields: list[str] | None = None,
) -> PriceBar:
    """
    Create a PriceBar with None/NaN values for testing NaN handling.

    Args:
        date_val: Price bar date
        nan_fields: List of fields to set to None (default: all OHLCV)

    Returns:
        PriceBar instance with None values
    """
    if nan_fields is None:
        nan_fields = ["open", "high", "low", "close", "volume", "adjusted_close"]

    kwargs: dict[str, Any] = {"date": date_val or date.today()}

    if "open" in nan_fields:
        kwargs["open"] = None
    if "high" in nan_fields:
        kwargs["high"] = None
    if "low" in nan_fields:
        kwargs["low"] = None
    if "close" in nan_fields:
        kwargs["close"] = None
    if "volume" in nan_fields:
        kwargs["volume"] = None
    if "adjusted_close" in nan_fields:
        kwargs["adjusted_close"] = None

    return PriceBar(**kwargs)


# --- KapFiling Factory ---

def create_kap_filing(
    symbol: str = "THYAO",
    title: str = "Test Filing",
    filing_type: str = "FR",
    disclosure_index: int = 12345678,
    pdf_url: str | None = None,
    source_url: str | None = None,
    published_at: datetime | None = None,
    provider: DataSource = DataSource.PYKAP,
    summary: str | None = None,
    attachment_count: int | None = None,
    is_late: bool | None = None,
    related_stocks: str | None = None,
) -> KapFiling:
    """
    Create a KapFiling instance for testing.

    Args:
        symbol: Stock symbol
        title: Filing title
        filing_type: Filing type code (FR, FAR, ODA, etc.)
        disclosure_index: KAP disclosure index (used to generate URLs)
        pdf_url: PDF download URL (auto-generated if not provided)
        source_url: Source page URL (auto-generated if not provided)
        published_at: Publication datetime (defaults to now)
        provider: Data source
        summary: Disclosure summary (from kap_sdk enrichment)
        attachment_count: Number of attachments
        is_late: Late disclosure flag
        related_stocks: Related stock symbols

    Returns:
        KapFiling instance
    """
    if pdf_url is None:
        pdf_url = f"https://www.kap.org.tr/tr/api/BildirimPdf/{disclosure_index}"
    if source_url is None:
        source_url = f"https://www.kap.org.tr/tr/Bildirim/{disclosure_index}"
    if published_at is None:
        published_at = datetime.now()

    return KapFiling(
        symbol=symbol.upper(),
        title=title,
        filing_type=filing_type,
        pdf_url=pdf_url,
        source_url=source_url,
        published_at=published_at,
        provider=provider,
        summary=summary,
        attachment_count=attachment_count,
        is_late=is_late,
        related_stocks=related_stocks,
    )


# --- FinancialStatementSet Factory ---

def create_financial_statement_set(
    symbol: str = "THYAO",
    period_type: PeriodType = PeriodType.ANNUAL,
    statement_date: date | None = None,
    source: DataSource = DataSource.BORSAPY,
    total_assets: float | None = 100_000_000_000,
    total_equity: float | None = 50_000_000_000,
    revenue: float | None = 50_000_000_000,
    net_income: float | None = 5_000_000_000,
    operating_cash_flow: float | None = 6_000_000_000,
    free_cash_flow: float | None = 4_000_000_000,
    **kwargs: Any,
) -> FinancialStatementSet:
    """
    Create a FinancialStatementSet instance for testing.

    Args:
        symbol: Stock symbol
        period_type: ANNUAL or QUARTERLY
        statement_date: Statement date (defaults to year-end)
        source: Data source
        total_assets: Total assets value
        total_equity: Total equity value
        revenue: Revenue value
        net_income: Net income value
        operating_cash_flow: Operating cash flow
        free_cash_flow: Free cash flow
        **kwargs: Additional FinancialStatementSet fields

    Returns:
        FinancialStatementSet instance
    """
    if statement_date is None:
        if period_type == PeriodType.ANNUAL:
            statement_date = date(2024, 12, 31)
        else:
            statement_date = date(2024, 9, 30)

    return FinancialStatementSet(
        symbol=symbol.upper(),
        period_type=period_type,
        statement_date=statement_date,
        source=source,
        total_assets=total_assets,
        total_equity=total_equity,
        revenue=revenue,
        net_income=net_income,
        operating_cash_flow=operating_cash_flow,
        free_cash_flow=free_cash_flow,
        **kwargs,
    )


def create_financial_statement_set_with_nan(
    symbol: str = "THYAO",
    nan_fields: list[str] | None = None,
) -> FinancialStatementSet:
    """
    Create a FinancialStatementSet with None values for testing NaN handling.

    Args:
        symbol: Stock symbol
        nan_fields: List of fields to set to None (default: all financial fields)

    Returns:
        FinancialStatementSet instance with None values
    """
    if nan_fields is None:
        nan_fields = [
            "total_assets", "total_equity", "revenue", "net_income",
            "operating_cash_flow", "free_cash_flow",
        ]

    return FinancialStatementSet(
        symbol=symbol.upper(),
        period_type=PeriodType.ANNUAL,
        statement_date=date(2024, 12, 31),
        **{field: None for field in nan_fields},
    )


# --- CompanyProfile Factory ---

def create_company_profile(
    symbol: str = "THYAO",
    company_name: str | None = None,
    sector: str | None = "Technology",
    industry: str | None = "Software",
    website: str | None = None,
    description: str | None = "Test company description",
    isin: str | None = None,
    exchange: str = "BIST",
    source: DataSource = DataSource.BORSAPY,
) -> CompanyProfile:
    """
    Create a CompanyProfile instance for testing.

    Args:
        symbol: Stock symbol
        company_name: Company name (defaults to symbol + " Company")
        sector: Sector name
        industry: Industry name
        website: Company website (auto-generated if not provided)
        description: Company description
        isin: ISIN code (auto-generated if not provided)
        exchange: Exchange name
        source: Data source

    Returns:
        CompanyProfile instance
    """
    if company_name is None:
        company_name = f"{symbol.upper()} Company"
    if website is None:
        website = f"https://www.{symbol.lower()}.com"
    if isin is None:
        isin = f"TR{symbol.upper()}12345"

    return CompanyProfile(
        symbol=symbol.upper(),
        company_name=company_name,
        sector=sector,
        industry=industry,
        website=website,
        description=description,
        isin=isin,
        exchange=exchange,
        source=source,
    )


# --- StockSnapshot Factory ---

def create_stock_snapshot(
    symbol: str = "THYAO",
    last_price: float = 250.50,
    change: float | None = 5.50,
    change_percent: float | None = 2.2,
    volume: float | None = 1_500_000,
    market_cap: float | None = 15_000_000_000,
    pe_ratio: float | None = 12.5,
    pb_ratio: float | None = 1.8,
    year_high: float | None = 280.00,
    year_low: float | None = 180.00,
    source: DataSource = DataSource.BORSAPY,
) -> StockSnapshot:
    """
    Create a StockSnapshot instance for testing.

    Args:
        symbol: Stock symbol
        last_price: Last traded price
        change: Price change
        change_percent: Percentage change
        volume: Trading volume
        market_cap: Market capitalization
        pe_ratio: P/E ratio
        pb_ratio: P/B ratio
        year_high: 52-week high
        year_low: 52-week low
        source: Data source

    Returns:
        StockSnapshot instance
    """
    return StockSnapshot(
        symbol=symbol.upper(),
        last_price=last_price,
        change=change,
        change_percent=change_percent,
        volume=volume,
        market_cap=market_cap,
        pe_ratio=pe_ratio,
        pb_ratio=pb_ratio,
        year_high=year_high,
        year_low=year_low,
        source=source,
    )


def create_stock_snapshot_with_nan(
    symbol: str = "THYAO",
    nan_fields: list[str] | None = None,
) -> StockSnapshot:
    """
    Create a StockSnapshot with None values for testing NaN handling.

    Args:
        symbol: Stock symbol
        nan_fields: List of fields to set to None

    Returns:
        StockSnapshot instance with None values
    """
    if nan_fields is None:
        nan_fields = ["pe_ratio", "pb_ratio", "fifty_day_avg", "two_hundred_day_avg"]

    base_kwargs: dict[str, Any] = {
        "symbol": symbol.upper(),
        "last_price": 250.0,
    }

    for field in nan_fields:
        base_kwargs[field] = None

    return StockSnapshot(**base_kwargs)


# --- ProviderCapabilities Factory ---

def create_provider_capabilities(
    supported_data: set[ProviderCapability] | None = None,
    supported_markets: set[str] | None = None,
    max_history_days: int = 3650,
    supports_intraday: bool = False,
    supports_quarterly_financials: bool = True,
    timeout_seconds: float = 30.0,
    retry_count: int = 3,
) -> ProviderCapabilities:
    """
    Create a ProviderCapabilities instance for testing.

    Args:
        supported_data: Set of supported capabilities
        supported_markets: Set of supported markets
        max_history_days: Maximum history days
        supports_intraday: Whether intraday data is supported
        supports_quarterly_financials: Whether quarterly financials are supported
        timeout_seconds: Timeout in seconds
        retry_count: Number of retries

    Returns:
        ProviderCapabilities instance
    """
    if supported_data is None:
        supported_data = {
            ProviderCapability.PRICE_HISTORY,
            ProviderCapability.METRICS,
        }
    if supported_markets is None:
        supported_markets = {"BIST"}

    return ProviderCapabilities(
        supported_data=supported_data,
        supported_markets=supported_markets,
        max_history_days=max_history_days,
        supports_intraday=supports_intraday,
        supports_quarterly_financials=supports_quarterly_financials,
        timeout_seconds=timeout_seconds,
        retry_count=retry_count,
    )


# --- Batch Factories ---

def create_price_bars_batch(
    symbol: str = "THYAO",
    num_bars: int = 5,
    start_date: date | None = None,
    base_price: float = 250.0,
) -> list[PriceBar]:
    """
    Create a batch of PriceBar instances.

    Args:
        symbol: Stock symbol (for logging)
        num_bars: Number of bars to create
        start_date: Start date (defaults to num_bars days ago)
        base_price: Base price for calculations

    Returns:
        List of PriceBar instances
    """
    if start_date is None:
        start_date = date.today()

    bars = []
    for i in range(num_bars):
        bars.append(create_price_bar(
            date_val=start_date if num_bars == 1 else date(
                start_date.year, start_date.month, start_date.day + i
            ) if i == 0 else date.fromordinal(start_date.toordinal() + i),
            open_price=base_price + i * 2,
            high=base_price + i * 2 + 5,
            low=base_price + i * 2 - 3,
            close=base_price + i * 2 + 1,
        ))

    return bars


def create_kap_filings_batch(
    symbol: str = "THYAO",
    num_filings: int = 3,
    filing_types: list[str] | None = None,
) -> list[KapFiling]:
    """
    Create a batch of KapFiling instances.

    Args:
        symbol: Stock symbol
        num_filings: Number of filings to create
        filing_types: List of filing types (cycles through default types)

    Returns:
        List of KapFiling instances
    """
    if filing_types is None:
        filing_types = ["FR", "FAR", "ODA"]

    filings = []
    for i in range(num_filings):
        filing_type = filing_types[i % len(filing_types)]
        filings.append(create_kap_filing(
            symbol=symbol,
            title=f"{symbol} Filing {i + 1}",
            filing_type=filing_type,
            disclosure_index=12345678 + i,
        ))

    return filings