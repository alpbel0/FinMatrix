"""Provider-agnostic KAP filing mock fixtures.

Wraps factories.py with scenario-specific helpers for scheduler
and KAP data service testing. Provider-specific mocks (mock_pykap,
mock_kap_sdk) handle raw SDK responses; this module provides
application-level KapFiling fixtures.

Key features:
- Pre-configured filing scenarios (FR, ODA, FAR)
- Batch generation for batch sync testing
- Edge cases for NaN handling tests
- Date-aware fixtures for scheduler testing

Usage:
    from tests.mocks.mock_kap import (
        create_financial_report_filing,
        create_material_event_filing,
        create_kap_filings_batch_for_scheduler,
    )

    filing = create_financial_report_filing("THYAO", year=2024)
    batch = create_kap_filings_batch_for_scheduler(["THYAO", "GARAN"])
"""

from datetime import datetime, timedelta

from app.services.data.provider_models import DataSource
from tests.factories import create_kap_filing


# --- Basic Fixture Wrappers ---

def create_standard_kap_filing(
    symbol: str = "THYAO",
    disclosure_index: int = 12345678,
    provider: DataSource = DataSource.PYKAP,
) -> "KapFiling":
    """Create a standard KAP filing with all fields populated.

    Args:
        symbol: Stock symbol
        disclosure_index: KAP disclosure index
        provider: Data source (PYKAP or KAPSDK)

    Returns:
        KapFiling instance with default values
    """
    return create_kap_filing(
        symbol=symbol,
        title=f"{symbol} - Standard Disclosure",
        filing_type="FR",
        disclosure_index=disclosure_index,
        provider=provider,
        summary="Standard disclosure summary text",
        attachment_count=2,
        is_late=False,
    )


# --- Scenario-Specific Fixtures ---

def create_financial_report_filing(
    symbol: str = "THYAO",
    year: int = 2024,
    quarter: str | None = None,
    disclosure_index: int = 12345678,
    provider: DataSource = DataSource.PYKAP,
) -> "KapFiling":
    """Create a financial report (FR) filing.

    Args:
        symbol: Stock symbol
        year: Report year
        quarter: Quarter string (e.g., "Q3") or None for annual
        disclosure_index: KAP disclosure index
        provider: Data source

    Returns:
        KapFiling instance with financial report details
    """
    period = f"{year}" if not quarter else f"{year} {quarter}"
    title = f"{symbol} - Finansal Rapor {period}"

    # Calculate approximate publish date
    if quarter:
        q_num = int(quarter[-1])
        month = q_num * 3
    else:
        month = 12
    published_at = datetime(year, month, 28, 14, 30)

    return create_kap_filing(
        symbol=symbol,
        title=title,
        filing_type="FR",
        disclosure_index=disclosure_index,
        provider=provider,
        published_at=published_at,
        summary=f"Financial report for {period}",
        attachment_count=3,
    )


def create_material_event_filing(
    symbol: str = "THYAO",
    event_title: str = "Olaylara Duyarlilik Bildirimi",
    disclosure_index: int = 12345679,
    provider: DataSource = DataSource.PYKAP,
    summary: str = "Material event summary - important disclosure",
) -> "KapFiling":
    """Create a material event (ODA) filing.

    Args:
        symbol: Stock symbol
        event_title: Event title suffix
        disclosure_index: KAP disclosure index
        provider: Data source
        summary: Disclosure summary text

    Returns:
        KapFiling instance with material event details
    """
    return create_kap_filing(
        symbol=symbol,
        title=f"{symbol} - {event_title}",
        filing_type="ODA",
        disclosure_index=disclosure_index,
        provider=provider,
        summary=summary,
        attachment_count=1,
        published_at=datetime.now() - timedelta(hours=2),
    )


def create_activity_report_filing(
    symbol: str = "THYAO",
    year: int = 2025,
    disclosure_index: int = 12345680,
) -> "KapFiling":
    """Create an activity report (FAR) filing.

    Args:
        symbol: Stock symbol
        year: Report year
        disclosure_index: KAP disclosure index

    Returns:
        KapFiling instance with activity report details
    """
    return create_kap_filing(
        symbol=symbol,
        title=f"{symbol} Faaliyet Raporu {year}",
        filing_type="FAR",
        disclosure_index=disclosure_index,
        published_at=datetime(year, 3, 31, 10, 0),
        summary=f"Activity report for {year}",
    )


def create_late_disclosure_filing(
    symbol: str = "THYAO",
    disclosure_index: int = 12345681,
) -> "KapFiling":
    """Create a late disclosure filing (is_late=True).

    Args:
        symbol: Stock symbol
        disclosure_index: KAP disclosure index

    Returns:
        KapFiling instance with is_late=True
    """
    return create_kap_filing(
        symbol=symbol,
        title=f"{symbol} - Late Disclosure",
        filing_type="FR",
        disclosure_index=disclosure_index,
        is_late=True,
        summary="This disclosure was submitted late",
        attachment_count=1,
    )


def create_multi_attachment_filing(
    symbol: str = "THYAO",
    attachment_count: int = 5,
    disclosure_index: int = 12345682,
) -> "KapFiling":
    """Create a filing with multiple attachments.

    Args:
        symbol: Stock symbol
        attachment_count: Number of attachments
        disclosure_index: KAP disclosure index

    Returns:
        KapFiling instance with specified attachment count
    """
    return create_kap_filing(
        symbol=symbol,
        title=f"{symbol} - Comprehensive Report",
        filing_type="FR",
        disclosure_index=disclosure_index,
        attachment_count=attachment_count,
        summary="Report with multiple attachments",
    )


# --- Batch Generation ---

def create_kap_filings_batch_for_scheduler(
    symbols: list[str] = ["THYAO", "GARAN", "AKBNK"],
    filing_types: list[str] = ["FR", "ODA"],
    days_back: int = 30,
    provider: DataSource = DataSource.PYKAP,
) -> list["KapFiling"]:
    """Create a batch of filings for scheduler testing.

    Generates filings for each symbol with specified types,
    distributed across the days_back period.

    Args:
        symbols: List of stock symbols
        filing_types: List of filing type codes
        days_back: Number of days to distribute publish dates
        provider: Data source

    Returns:
        List of KapFiling instances
    """
    filings = []
    base_index = 12345678

    for i, symbol in enumerate(symbols):
        for j, filing_type in enumerate(filing_types):
            # Distribute publish dates across the period
            days_offset = (i * len(filing_types) + j) % days_back
            published_at = datetime.now() - timedelta(days=days_offset)

            filing = create_kap_filing(
                symbol=symbol,
                title=f"{symbol} - {filing_type} Filing",
                filing_type=filing_type,
                disclosure_index=base_index + i * len(filing_types) + j,
                provider=provider,
                published_at=published_at,
            )
            filings.append(filing)

    return filings


def create_kap_filings_for_single_symbol(
    symbol: str = "THYAO",
    num_filings: int = 5,
    filing_types: list[str] = ["FR", "ODA", "FAR"],
) -> list["KapFiling"]:
    """Create multiple filings for a single symbol.

    Args:
        symbol: Stock symbol
        num_filings: Number of filings to create
        filing_types: Filing type codes to cycle through

    Returns:
        List of KapFiling instances for the symbol
    """
    filings = []
    base_index = 12345678

    for i in range(num_filings):
        filing_type = filing_types[i % len(filing_types)]
        published_at = datetime.now() - timedelta(days=i)

        filing = create_kap_filing(
            symbol=symbol,
            title=f"{symbol} - Filing {i + 1}",
            filing_type=filing_type,
            disclosure_index=base_index + i,
            published_at=published_at,
        )
        filings.append(filing)

    return filings


# --- Edge Cases ---

def create_kap_filing_with_missing_fields(
    symbol: str = "THYAO",
    missing_fields: list[str] | None = None,
) -> "KapFiling":
    """Create a filing with None values for testing NaN handling.

    Args:
        symbol: Stock symbol
        missing_fields: Fields to set to None (default: summary, attachment_count, pdf_url)

    Returns:
        KapFiling instance with None values in specified fields
    """
    if missing_fields is None:
        missing_fields = ["summary", "attachment_count", "pdf_url"]

    return create_kap_filing(
        symbol=symbol,
        title=f"{symbol} - Incomplete Filing",
        filing_type="FR",
        disclosure_index=12345683,
        summary=None if "summary" in missing_fields else "Summary text",
        attachment_count=None if "attachment_count" in missing_fields else 1,
        pdf_url=None if "pdf_url" in missing_fields else "https://test.com/pdf",
    )


def create_kap_filing_with_related_stocks(
    symbol: str = "THYAO",
    related_stocks: str = "GARAN,AKBNK",
) -> "KapFiling":
    """Create a filing with related stocks (JSONB field).

    Args:
        symbol: Primary stock symbol
        related_stocks: Comma-separated related stock symbols

    Returns:
        KapFiling instance with related_stocks field populated
    """
    return create_kap_filing(
        symbol=symbol,
        title=f"{symbol} - Joint Disclosure",
        filing_type="ODA",
        disclosure_index=12345684,
        related_stocks=related_stocks,
        summary="Disclosure involving multiple companies",
    )


def create_empty_kap_filing_list() -> list["KapFiling"]:
    """Return an empty filing list for edge case testing.

    Returns:
        Empty list (for testing empty response handling)
    """
    return []


# --- Error Injection Helpers ---

def create_filing_with_invalid_disclosure_index() -> "KapFiling":
    """Create a filing with invalid disclosure index for error testing.

    Returns:
        KapFiling instance that would fail URL resolution
    """
    return create_kap_filing(
        symbol="INVALID",
        title="Invalid Filing",
        filing_type="FR",
        disclosure_index=-1,
        pdf_url=None,
        source_url=None,
    )


# --- DB-Ready Dict Helpers ---

def create_kap_filing_dict_for_mapper(
    symbol: str = "THYAO",
    disclosure_index: int = 12345678,
) -> dict:
    """Create a dict ready for kap_report_mapper.py upsert.

    Args:
        symbol: Stock symbol
        disclosure_index: KAP disclosure index

    Returns:
        Dict matching KapFiling model fields
    """
    filing = create_kap_filing(
        symbol=symbol,
        disclosure_index=disclosure_index,
    )
    return {
        "symbol": filing.symbol,
        "title": filing.title,
        "filing_type": filing.filing_type,
        "pdf_url": filing.pdf_url,
        "source_url": filing.source_url,
        "published_at": filing.published_at,
        "provider": filing.provider.value,
        "summary": filing.summary,
        "attachment_count": filing.attachment_count,
        "is_late": filing.is_late,
        "related_stocks": filing.related_stocks,
    }