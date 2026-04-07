"""kap_sdk-based KAP disclosure provider implementation.

Provides fallback KAP disclosure fetching using kap_sdk package.
Uses ThreadPoolExecutor for async-to-sync bridge.
"""

import asyncio
import os
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

# pyppeteer 2.0.0 defaults to Chromium revision 1181205 on Windows, which
# currently 404s. Override to a known-good revision unless the environment
# explicitly sets its own value.
os.environ.setdefault("PYPPETEER_CHROMIUM_REVISION", "1181217")

# Optional import - graceful degrade if kap_sdk not installed
_KAP_SDK_AVAILABLE = False
_KapClient = None
_AnnouncementType = None
_MemberType = None


def _patched_browser_config() -> dict[str, Any]:
    """Return pyppeteer config with correct boolean signal flags."""
    config: dict[str, Any] = {
        "handleSIGINT": False,
        "handleSIGTERM": False,
        "handleSIGHUP": False,
        "headless": True,
        "args": [
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--disable-web-security",
            "--disable-features=IsolateOrigins,site-per-process",
        ],
    }

    chrome_path = os.environ.get("KAP_SDK_BROWSER_PATH")
    if chrome_path and Path(chrome_path).exists():
        config["executablePath"] = chrome_path

    return config

try:
    import kap_sdk
    import kap_sdk._companies as kap_sdk_companies_module
    import kap_sdk._company_info as kap_sdk_company_info_module
    import kap_sdk._indices as kap_sdk_indices_module
    import kap_sdk._sectors as kap_sdk_sectors_module
    import kap_sdk.models.company as kap_sdk_company_model
    import kap_sdk.models.company_info as kap_sdk_company_info_model
    from kap_sdk.kap_client import KapClient
    from kap_sdk.models.announcement_type import AnnouncementType, MemberType

    kap_sdk._get_browser_config = _patched_browser_config
    kap_sdk_companies_module._get_browser_config = _patched_browser_config
    kap_sdk_company_info_module._get_browser_config = _patched_browser_config
    kap_sdk_indices_module._get_browser_config = _patched_browser_config
    kap_sdk_sectors_module._get_browser_config = _patched_browser_config
    kap_sdk_company_model._get_browser_config = _patched_browser_config
    kap_sdk_company_info_model._get_browser_config = _patched_browser_config

    _KAP_SDK_AVAILABLE = True
    _KapClient = KapClient
    _AnnouncementType = AnnouncementType
    _MemberType = MemberType
except ImportError:
    pass  # kap_sdk not installed, provider will be unavailable

from app.services.data.provider_interface import BaseMarketDataProvider
from app.services.data.provider_models import (
    CompanyProfile,
    DataSource,
    FinancialStatementSet,
    KapFiling,
    PeriodType,
    PriceBar,
    ProviderCapabilities,
    ProviderCapability,
    StockSnapshot,
)
from app.services.data.provider_exceptions import (
    ProviderConnectionError,
    ProviderDataNotFoundError,
    ProviderError,
    ProviderRateLimitError,
    ProviderSymbolNotFoundError,
    ProviderTimeoutError,
    ProviderAPIError,
)
from app.services.utils.logging import logger


def map_kap_sdk_exception(exc: Exception) -> ProviderError:
    """Map kap_sdk exceptions to provider exceptions.

    kap_sdk raises:
    - requests.HTTPError: API failures
    - pyppeteer errors: Browser/scraping failures
    - KeyError/AttributeError: Missing data fields
    - asyncio.TimeoutError: Async timeout
    - Generic Exception: Various scraping failures
    """
    exc_str = str(exc).lower()

    # Network/connection errors
    if "connection" in exc_str or "network" in exc_str or isinstance(exc, ConnectionError):
        return ProviderConnectionError(str(exc), provider="kap_sdk")

    # Timeout errors
    if isinstance(exc, (TimeoutError, asyncio.TimeoutError)):
        return ProviderTimeoutError(timeout_seconds=30.0, provider="kap_sdk")

    # HTTP errors with status code
    if hasattr(exc, 'status_code') or 'status' in exc_str:
        status_code = getattr(exc, 'status_code', None)
        if status_code == 404 or "not found" in exc_str:
            return ProviderDataNotFoundError(
                symbol="unknown",
                data_type="disclosure",
                provider="kap_sdk"
            )
        if status_code == 429 or "rate limit" in exc_str:
            return ProviderRateLimitError(provider="kap_sdk")
        return ProviderAPIError(str(exc), status_code=status_code, provider="kap_sdk")

    # Symbol not found (company lookup failed)
    if "not found" in exc_str or "company" in exc_str:
        return ProviderSymbolNotFoundError(symbol="unknown", provider="kap_sdk")

    # Fallback: wrap as generic ProviderError
    return ProviderError(str(exc), provider="kap_sdk")


class KapSdkProvider(BaseMarketDataProvider):
    """
    kap_sdk-based KAP disclosure provider for BIST stocks.

    Uses kap_sdk package (async-first) for KAP disclosures.
    Implements async-to-sync bridge via ThreadPoolExecutor.

    Capabilities:
    - KAP_FILINGS (primary) - disclosure metadata from KAP.org.tr

    Does NOT support:
    - Price history (use borsapy)
    - Financial statements (use borsapy)
    - Stock snapshots/metrics (use borsapy)
    - Company profile (use pykap - simpler chain)
    """

    # Singleton KapClient instance (type as Any since import is optional)
    _client: Any = None
    _companies_cache: list[Any] | None = None

    def __init__(self, timeout: float = 30.0, retry_count: int = 3):
        super().__init__(timeout=timeout, retry_count=retry_count)

        # Reusable thread pool for async operations
        self._executor = ThreadPoolExecutor(max_workers=4)

        logger.info("Initializing KapSdkProvider")

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supported_data={
                ProviderCapability.KAP_FILINGS,
            },
            supported_markets={"BIST"},
            max_history_days=3650,  # KAP has historical data
            supports_intraday=False,
            supports_quarterly_financials=False,
            timeout_seconds=self._timeout,
            retry_count=self._retry_count,
        )

    def is_available(self) -> bool:
        """Check if kap_sdk is installed and operational."""
        return _KAP_SDK_AVAILABLE

    # --- Async methods (run via thread pool) ---

    async def _async_init_client(self) -> Any | None:
        """Initialize KapClient instance."""
        if not _KAP_SDK_AVAILABLE:
            return None

        if self._client is None:
            self._client = _KapClient(
                cache_expiry=3600,          # 1 hour cache TTL
                company_cache_expiry=86400,  # 24 hour company list cache
            )
        return self._client

    async def _async_get_company(self, symbol: str) -> Any | None:
        """Get Company object from kap_sdk.

        Company lookup chain:
        1. Fetch all companies (cached 24h)
        2. Filter by code (ticker symbol)
        """
        client = await self._async_init_client()
        if client is None:
            return None

        # Use cached companies if available
        if self._companies_cache is None:
            self._companies_cache = await client.get_companies()

        for company in self._companies_cache:
            if company.code == symbol.upper():
                return company

        return None

    async def _async_get_announcements(
        self,
        company: Any,
        fromdate: date,
        todate: date,
        disclosure_types: list[Any] | None = None,
    ) -> list[Any]:
        """Get announcements/disclosures from kap_sdk."""
        client = await self._async_init_client()
        if client is None:
            return []

        announcements = await client.get_announcements(
            company=company,
            fromdate=fromdate,
            todate=todate,
            disclosure_type=disclosure_types,
        )

        return announcements

    async def _async_get_kap_filings(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        filing_types: Sequence[str] | None = None,
    ) -> list[KapFiling]:
        """Async implementation of get_kap_filings."""
        filings: list[KapFiling] = []

        # Step 1: Get Company object
        company = await self._async_get_company(symbol)
        if company is None:
            raise ProviderSymbolNotFoundError(symbol=symbol.upper(), provider="kap_sdk")

        # Step 2: Map filing types to kap_sdk AnnouncementType
        disclosure_types = self._map_filing_types_to_announcement_types(filing_types)

        # Step 3: Get announcements
        try:
            announcements = await self._async_get_announcements(
                company=company,
                fromdate=start_date,
                todate=end_date,
                disclosure_types=disclosure_types,
            )

            for announcement in announcements:
                filing = self._map_announcement_to_filing(announcement, symbol)
                if filing:
                    filings.append(filing)

        except Exception as exc:
            logger.warning(f"Failed to fetch announcements for {symbol}: {exc}")
            # Don't raise - return empty or partial results

        # Sort by published_at descending
        filings.sort(key=lambda f: f.published_at or datetime.min, reverse=True)

        return filings

    # --- Sync interface methods (bridge to async) ---

    def get_kap_filings(
        self,
        symbol: str,
        start_date: date | None = None,
        filing_types: Sequence[str] | None = None,
    ) -> Sequence[KapFiling]:
        """
        Fetch KAP (Public Disclosure Platform) filings for a stock.

        Args:
            symbol: BIST stock symbol (THYAO, GARAN, etc.)
            start_date: Optional filter for filings after this date.
                        Default: last 30 days if not specified.
            filing_types: Optional filter for specific filing types (FR, ODA, etc.)

        Returns:
            List of KapFiling objects with disclosure metadata.
        """
        if not self.is_available():
            raise ProviderError("kap_sdk not installed", provider="kap_sdk")

        logger.debug(f"Fetching KAP filings for {symbol} via kap_sdk")

        # Default date range
        if start_date is None:
            start_date = date.today() - timedelta(days=30)
        end_date = date.today()

        try:
            # Run async via thread pool
            future = self._executor.submit(
                asyncio.run,
                self._async_get_kap_filings(symbol, start_date, end_date, filing_types)
            )
            result = future.result(timeout=self._timeout)
            logger.info(f"Fetched {len(result)} KAP filings for {symbol} via kap_sdk")
            return result

        except TimeoutError as exc:
            raise ProviderTimeoutError(timeout_seconds=self._timeout, provider="kap_sdk")
        except Exception as exc:
            logger.error(f"Error fetching KAP filings for {symbol}: {exc}")
            raise map_kap_sdk_exception(exc)

    # --- Mapping methods ---

    def _map_filing_types_to_announcement_types(
        self,
        filing_types: Sequence[str] | None,
    ) -> list[Any] | None:
        """Map filing type strings to kap_sdk AnnouncementType enum values."""
        if not _KAP_SDK_AVAILABLE or filing_types is None:
            return None

        type_mapping = {
            "FR": [_AnnouncementType.FinancialStatement],
            "ODA": [_AnnouncementType.MaterialEventDisclosure],
            "DUY": [_AnnouncementType.RegulatoryAuthorityAnnouncements],
            "DG": [_AnnouncementType.Other],
            "CA": [_AnnouncementType.Corporate_Actions],
        }

        result = []
        for ft in filing_types:
            if ft in type_mapping:
                result.extend(type_mapping[ft])

        return result if result else None

    def _map_announcement_to_filing(
        self,
        announcement: Any,
        symbol: str,
    ) -> KapFiling | None:
        """Map kap_sdk Disclosure/announcement to KapFiling model."""
        try:
            # kap_sdk Disclosure has disclosureBasic attribute
            basic = announcement.disclosureBasic

            # Extract disclosureIndex for URLs
            disclosure_index = basic.disclosureIndex

            source_url = f"https://www.kap.org.tr/tr/Bildirim/{disclosure_index}"
            pdf_url = f"https://www.kap.org.tr/tr/api/BildirimPdf/{disclosure_index}"

            # Parse publishDate format: "dd.mm.yyyy HH:MM:SS"
            published_at = self._parse_kap_publish_date(basic.publishDate)

            # Map disclosureClass to filing_type
            filing_type = basic.disclosureClass or basic.disclosureType or "UNK"

            # Extract enrichment fields from disclosureDetail
            summary = None
            attachment_count = basic.attachmentCount if hasattr(basic, 'attachmentCount') else None
            is_late = basic.isLate if hasattr(basic, 'isLate') else None
            related_stocks = basic.relatedStocks if hasattr(basic, 'relatedStocks') else None

            # Try to get summary from disclosureDetail if available
            if hasattr(announcement, 'disclosureDetail') and announcement.disclosureDetail:
                summary = getattr(announcement.disclosureDetail, 'summary', None)

            return KapFiling(
                symbol=symbol.upper(),
                title=basic.title,
                filing_type=filing_type,
                pdf_url=pdf_url,
                source_url=source_url,
                published_at=published_at,
                provider=DataSource.KAPSDK,
                summary=summary,
                attachment_count=attachment_count,
                is_late=is_late,
                related_stocks=related_stocks,
            )

        except Exception as exc:
            logger.debug(f"Failed to map announcement for {symbol}: {exc}")
            return None

    def _parse_kap_publish_date(self, date_str: str | None) -> datetime | None:
        """Parse kap_sdk publishDate format: "dd.mm.yyyy HH:MM:SS"."""
        if not date_str:
            return None

        try:
            # kap_sdk format: "29.12.2025 19:21:18"
            return datetime.strptime(date_str.strip(), "%d.%m.%Y %H:%M:%S")
        except ValueError:
            # Try alternative formats
            for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%d.%m.%Y"):
                try:
                    return datetime.strptime(date_str.strip(), fmt)
                except ValueError:
                    continue
            return None

    # --- Methods not supported by kap_sdk (delegated to primary or return empty) ---

    def get_price_history(
        self,
        symbol: str,
        start_date: date | None = None,
        end_date: date | None = None,
        period: str | None = None,
    ) -> Sequence[PriceBar]:
        """kap_sdk does not provide price history. Returns empty list."""
        logger.warning(f"kap_sdk does not support price history for {symbol}")
        return []

    def get_stock_snapshot(self, symbol: str) -> StockSnapshot:
        """kap_sdk does not provide stock snapshots."""
        raise ProviderDataNotFoundError(
            symbol=symbol,
            data_type="snapshot",
            provider="kap_sdk"
        )

    def get_financial_statements(
        self,
        symbol: str,
        period_type: PeriodType = PeriodType.ANNUAL,
        last_n: int = 5,
    ) -> Sequence[FinancialStatementSet]:
        """kap_sdk financial reports are different format. Returns empty list."""
        logger.warning(f"kap_sdk financial statements not mapped for {symbol}")
        return []

    def get_company_profile(self, symbol: str) -> CompanyProfile:
        """kap_sdk company profile requires complex lookup chain. Use pykap instead."""
        raise ProviderDataNotFoundError(
            symbol=symbol,
            data_type="company_profile",
            provider="kap_sdk"
        )

    def batch_price_update(
        self,
        symbols: Sequence[str],
        period: str = "1mo",
    ) -> dict[str, Sequence[PriceBar]]:
        """kap_sdk does not support batch price updates."""
        return {}

    def health_check(self) -> bool:
        """Verify kap_sdk provider is operational."""
        if not self.is_available():
            logger.debug("kap_sdk not installed, health check skipped")
            return False

        try:
            # Quick test - fetch a company
            future = self._executor.submit(
                asyncio.run,
                self._async_get_company("THYAO")
            )
            company = future.result(timeout=10.0)

            if company is not None:
                logger.debug("kap_sdk health check passed")
                return True

            logger.warning("kap_sdk health check: THYAO company not found")
            return False

        except Exception as e:
            logger.warning(f"kap_sdk health check failed: {e}")
            return False

    def __del__(self):
        """Cleanup thread pool on destruction."""
        if hasattr(self, '_executor'):
            self._executor.shutdown(wait=False)
