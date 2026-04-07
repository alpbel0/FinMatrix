"""Pykap KAP disclosure provider implementation."""

import sys
from collections.abc import Sequence
from datetime import date, datetime, timedelta
from pathlib import Path

# Add pykap to path (it's in search/pykap)
pykap_path = Path(__file__).parent.parent.parent.parent.parent.parent / "search" / "pykap"
if pykap_path.exists():
    sys.path.insert(0, str(pykap_path))

# Direct imports from pykap submodules (avoiding __init__.py issues)
from pykap.bist.BISTCompany import BISTCompany
from pykap.get_general_info import get_general_info

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
    ProviderDataNotFoundError,
    ProviderError,
    ProviderSymbolNotFoundError,
    map_pykap_exception,
)
from app.services.utils.logging import logger


# KAP disclosure subject UUIDs (from pykap documentation)
KAP_SUBJECT_FINANCIAL_REPORT = "4028328c594bfdca01594c0af9aa0057"  # Finansal Rapor
KAP_SUBJECT_OPERATING_REPORT = "4028328d594c04f201594c5155dd0076"  # Faaliyet Raporu

# Valid disclosure types from pykap
VALID_DISCLOSURE_TYPES = {"FAR", "KYUR", "SUR", "KDP", "DEG", "UNV", "SYI"}
DISCLOSURE_DATE_FIELDS = (
    "publishDate",
    "disclosureDate",
    "updateDate",
    "indexedDate",
    "date",
)


class PykapProvider(BaseMarketDataProvider):
    """
    Pykap-based KAP disclosure provider for BIST stocks.

    Uses pykap for:
    - KAP filings/disclosures (via KAP.org.tr API)
    - Company search and general info

    Capabilities:
    - KAP_FILINGS (primary) - detailed filing metadata with search
    - COMPANY_PROFILE - basic company info from KAP

    Does NOT support:
    - Price history (use borsapy)
    - Financial statements (use borsapy)
    - Stock snapshots/metrics (use borsapy)
    """

    def __init__(self, timeout: float = 30.0, retry_count: int = 3):
        super().__init__(timeout=timeout, retry_count=retry_count)
        logger.info("Initializing PykapProvider")

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supported_data={
                ProviderCapability.KAP_FILINGS,
                ProviderCapability.COMPANY_PROFILE,
            },
            supported_markets={"BIST"},
            max_history_days=3650,  # KAP has historical data
            supports_intraday=False,
            supports_quarterly_financials=False,
            timeout_seconds=self._timeout,
            retry_count=self._retry_count,
        )

    def _create_company(self, symbol: str) -> BISTCompany:
        """Create pykap BISTCompany instance with error handling."""
        try:
            company = BISTCompany(symbol.upper())
            return company
        except ValueError as exc:
            # pykap raises ValueError for invalid ticker
            raise ProviderSymbolNotFoundError(symbol=symbol.upper(), provider="pykap")
        except Exception as exc:
            mapped_exc = map_pykap_exception(exc)
            logger.error(f"Failed to create company for {symbol}: {mapped_exc}")
            raise mapped_exc

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
            filing_types: Optional filter for specific filing types (FR, FAR, etc.)

        Returns:
            List of KapFiling objects with disclosure metadata.
        """
        logger.debug(f"Fetching KAP filings for {symbol}")

        # Default to last 30 days if start_date not specified
        if start_date is None:
            start_date = date.today() - timedelta(days=30)

        end_date = date.today()

        try:
            company = self._create_company(symbol)
            filings: list[KapFiling] = []

            # Fetch financial reports (FR) via historical disclosure list
            try:
                fr_disclosures = company.get_historical_disclosure_list(
                    fromdate=start_date,
                    todate=end_date,
                    disclosure_type="FR",
                    subject=KAP_SUBJECT_FINANCIAL_REPORT,
                )

                for disc in fr_disclosures:
                    filing = self._map_disclosure_to_filing(disc, symbol, "FR")
                    if filing:
                        filings.append(filing)

            except Exception as exc:
                logger.warning(f"Failed to fetch FR disclosures for {symbol}: {exc}")

            # Fetch other disclosure types via get_disclosures if requested
            # or fetch FAR (activity reports) by default as they're important
            types_to_fetch = filing_types if filing_types else ["FAR"]

            for disc_type in types_to_fetch:
                if disc_type == "FR":
                    continue  # Already fetched via historical list

                if disc_type not in VALID_DISCLOSURE_TYPES:
                    logger.warning(f"Skipping invalid disclosure type: {disc_type}")
                    continue

                try:
                    disclosures = company.get_disclosures(disc_type)

                    for disc in disclosures:
                        # Filter by resolved disclosure date. When a filtered
                        # query cannot resolve any date, skip the record rather
                        # than leaking stale filings into a recent-only result.
                        pub_date = self._extract_disclosure_datetime(disc)
                        if pub_date is None:
                            logger.debug(
                                f"Skipping undated {disc_type} disclosure for {symbol}: "
                                f"{disc.get('disclosureIndex')}"
                            )
                            continue

                        if pub_date.date() < start_date:
                            continue

                        filing = self._map_disclosure_basic_to_filing(
                            disc,
                            symbol,
                            disc_type,
                            published_at=pub_date,
                        )
                        if filing:
                            filings.append(filing)

                except Exception as exc:
                    logger.warning(f"Failed to fetch {disc_type} disclosures for {symbol}: {exc}")

            # Sort by published_at descending (most recent first)
            filings.sort(key=lambda f: f.published_at or datetime.min, reverse=True)

            logger.info(f"Fetched {len(filings)} KAP filings for {symbol}")
            return filings

        except ProviderError:
            raise
        except Exception as exc:
            logger.error(f"Error fetching KAP filings for {symbol}: {exc}")
            raise map_pykap_exception(exc)

    def _map_disclosure_to_filing(
        self,
        disclosure: dict,
        symbol: str,
        filing_type: str,
    ) -> KapFiling | None:
        """Map historical disclosure dict to KapFiling model."""
        try:
            disclosure_index = disclosure.get("disclosureIndex")
            if not disclosure_index:
                return None

            # KAP exposes the downloadable PDF via the API route below.
            source_url = f"https://www.kap.org.tr/tr/Bildirim/{disclosure_index}"
            pdf_url = f"https://www.kap.org.tr/tr/api/BildirimPdf/{disclosure_index}"

            # Parse publish date if available
            year = disclosure.get("year")
            rule_type = disclosure.get("ruleType") or disclosure.get("ruleTypeTerm", "")
            # Construct approximate date from year and term
            published_at = None
            if year:
                # Financial reports typically published at end of period
                # Use year-end as approximation if exact date not available
                try:
                    term_clean = rule_type.replace(" ", "").strip()
                    if term_clean and "Q" in term_clean:
                        # Quarterly: parse Q1, Q2, Q3, Q4
                        quarter = int(term_clean[-1])
                        month = quarter * 3
                        published_at = datetime(year, month, 28 if month in [6, 9] else 30 if month in [4, 6, 9, 11] else 31)
                    else:
                        # Annual: year-end
                        published_at = datetime(year, 12, 31)
                except Exception:
                    published_at = datetime(year, 12, 31)

            # Build title from available info
            title_parts = []
            if year:
                title_parts.append(str(year))
            if rule_type:
                title_parts.append(rule_type.strip())
            title = "Finansal Rapor" if not title_parts else f"Finansal Rapor - {' '.join(title_parts)}"

            return KapFiling(
                symbol=symbol.upper(),
                title=title,
                filing_type=filing_type,
                pdf_url=pdf_url,
                source_url=source_url,
                published_at=published_at,
                provider=DataSource.PYKAP,
            )

        except Exception as exc:
            logger.debug(f"Failed to map disclosure for {symbol}: {exc}")
            return None

    def _map_disclosure_basic_to_filing(
        self,
        disclosure: dict,
        symbol: str,
        filing_type: str,
        published_at: datetime | None = None,
    ) -> KapFiling | None:
        """Map disclosureBasic dict to KapFiling model."""
        try:
            disclosure_index = disclosure.get("disclosureIndex")
            if not disclosure_index:
                return None

            title = disclosure.get("title", "")
            if not title:
                # Build title from year/period if available
                year = disclosure.get("year")
                period = disclosure.get("period")
                if year:
                    title = f"{filing_type} - {year}"
                    if period:
                        title += f" {period}"

            source_url = f"https://www.kap.org.tr/tr/Bildirim/{disclosure_index}"
            pdf_url = f"https://www.kap.org.tr/tr/api/BildirimPdf/{disclosure_index}"

            if published_at is None:
                published_at = self._extract_disclosure_datetime(disclosure)

            return KapFiling(
                symbol=symbol.upper(),
                title=title,
                filing_type=filing_type,
                pdf_url=pdf_url,
                source_url=source_url,
                published_at=published_at,
                provider=DataSource.PYKAP,
            )

        except Exception as exc:
            logger.debug(f"Failed to map disclosureBasic for {symbol}: {exc}")
            return None

    def _extract_disclosure_datetime(self, disclosure: dict) -> datetime | None:
        """Resolve the best available datetime field from a disclosure payload."""
        for field_name in DISCLOSURE_DATE_FIELDS:
            parsed = self._parse_publish_date(disclosure.get(field_name))
            if parsed is not None:
                return parsed
        return None

    def _parse_publish_date(self, date_value: str | datetime | None) -> datetime | None:
        """Parse KAP date strings from disclosure payloads."""
        if not date_value:
            return None

        if isinstance(date_value, datetime):
            return date_value

        if not isinstance(date_value, str):
            return None

        cleaned = date_value.strip()
        if not cleaned:
            return None

        try:
            # Common KAP format from disclosureBasic payloads.
            return datetime.strptime(cleaned, "%d.%m.%Y %H:%M:%S")
        except Exception:
            pass

        for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(cleaned, fmt)
            except ValueError:
                continue

        try:
            normalized = cleaned.replace("Z", "+00:00")
            return datetime.fromisoformat(normalized)
        except Exception:
            return None

    def get_company_profile(self, symbol: str) -> CompanyProfile:
        """
        Fetch company metadata from KAP.

        Args:
            symbol: BIST stock symbol

        Returns:
            CompanyProfile with basic company info.

        Note:
            Pykap provides limited profile data compared to borsapy.
            Use borsapy for more detailed profiles (sector, industry, etc.)
        """
        logger.debug(f"Fetching company profile for {symbol}")

        try:
            # Use pykap's get_general_info for basic company data
            info = get_general_info(symbol.upper())

            if info is None:
                raise ProviderSymbolNotFoundError(symbol=symbol.upper(), provider="pykap")

            profile = CompanyProfile(
                symbol=symbol.upper(),
                company_name=info.get("name"),
                # Pykap doesn't provide sector/industry - those come from borsapy
                sector=None,
                industry=None,
                website=info.get("summary_page"),  # KAP summary page URL
                description=None,  # No description from pykap
                isin=None,  # Not available from pykap
                exchange="BIST",
                source=DataSource.PYKAP,
            )

            logger.debug(f"Profile fetched for {symbol}: name={profile.company_name}")
            return profile

        except ProviderError:
            raise
        except Exception as exc:
            logger.error(f"Error fetching profile for {symbol}: {exc}")
            raise map_pykap_exception(exc)

    # --- Methods not supported by pykap ---

    def get_price_history(
        self,
        symbol: str,
        start_date: date | None = None,
        end_date: date | None = None,
        period: str | None = None,
    ) -> Sequence[PriceBar]:
        """Pykap does not provide price history. Returns empty list."""
        logger.warning(f"Pykap does not support price history for {symbol}")
        return []

    def get_stock_snapshot(self, symbol: str) -> StockSnapshot:
        """Pykap does not provide stock snapshots."""
        raise ProviderDataNotFoundError(
            symbol=symbol,
            data_type="snapshot",
            provider="pykap"
        )

    def get_financial_statements(
        self,
        symbol: str,
        period_type: PeriodType = PeriodType.ANNUAL,
        last_n: int = 5,
    ) -> Sequence[FinancialStatementSet]:
        """Pykap financial reports are parsed differently. Returns empty list."""
        logger.warning(f"Pykap financial statements not mapped for {symbol}")
        return []

    def batch_price_update(
        self,
        symbols: Sequence[str],
        period: str = "1mo",
    ) -> dict[str, Sequence[PriceBar]]:
        """Pykap does not support batch price updates."""
        return {}

    def health_check(self) -> bool:
        """Verify pykap provider is operational."""
        try:
            # Quick test with a well-known symbol
            info = get_general_info("THYAO")
            if info is not None:
                logger.debug("Pykap health check passed")
                return True
            return False
        except Exception as e:
            logger.warning(f"Pykap health check failed: {e}")
            return False
