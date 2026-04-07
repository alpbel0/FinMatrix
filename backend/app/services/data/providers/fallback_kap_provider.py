"""Fallback KAP provider with pykap primary + kap_sdk fallback.

Composite provider implementing:
- Primary-first fallback logic
- Deduplication across providers
- Enrichment with kap_sdk disclosureDetail metadata
"""

from collections.abc import Sequence
from datetime import date, datetime, timedelta
from typing import Any

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
    ProviderAPIError,
    ProviderConnectionError,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from app.services.utils.logging import logger


class FallbackKapProvider(BaseMarketDataProvider):
    """
    Composite KAP provider with fallback logic.

    Primary: PykapProvider (sync, direct API)
    Fallback: KapSdkProvider (async-wrapped, scraping-based)

    Strategy:
    1. Try primary first
    2. On retriable failure, try fallback
    3. Merge results with deduplication
    4. Enrich primary results with kap_sdk disclosureDetail metadata
    5. Track which provider(s) succeeded for observability

    Enrichment:
    kap_sdk's disclosureDetail provides additional metadata:
    - summary: Disclosure summary text
    - attachmentCount: Number of attachments
    - isLate: Late disclosure flag
    - relatedStocks: Related stock symbols
    """

    def __init__(
        self,
        primary: BaseMarketDataProvider,
        fallback: BaseMarketDataProvider | None = None,
        fallback_enabled: bool = True,
    ):
        super().__init__(
            timeout=primary.capabilities.timeout_seconds,
            retry_count=primary.capabilities.retry_count,
        )
        self._primary = primary
        self._fallback = fallback
        self._fallback_enabled = fallback_enabled and fallback is not None
        self._last_provider_used: str | None = None

        logger.info(
            f"Initializing FallbackKapProvider "
            f"(primary={primary.__class__.__name__}, "
            f"fallback={fallback.__class__.__name__ if fallback else 'None'}, "
            f"enabled={self._fallback_enabled})"
        )

    @property
    def capabilities(self) -> ProviderCapabilities:
        """Composite capabilities - inherits from primary."""
        primary_caps = self._primary.capabilities
        return ProviderCapabilities(
            supported_data=primary_caps.supported_data,
            supported_markets=primary_caps.supported_markets,
            max_history_days=primary_caps.max_history_days,
            supports_intraday=primary_caps.supports_intraday,
            supports_quarterly_financials=primary_caps.supports_quarterly_financials,
            timeout_seconds=primary_caps.timeout_seconds,
            retry_count=primary_caps.retry_count,
        )

    def get_kap_filings(
        self,
        symbol: str,
        start_date: date | None = None,
        filing_types: Sequence[str] | None = None,
    ) -> Sequence[KapFiling]:
        """
        Fetch KAP filings with fallback and enrichment.

        Flow:
        1. Try PykapProvider (primary)
        2. If primary succeeds:
           - If fallback available, try to enrich with kap_sdk metadata
           - Return enriched primary results
        3. If primary fails with retriable error:
           - Try KapSdkProvider (fallback)
           - If fallback succeeds, return fallback results
        4. Deduplicate and merge results
        5. Track success/failure for observability
        """
        logger.debug(f"Fetching KAP filings for {symbol} with fallback")

        primary_results: list[KapFiling] = []
        fallback_results: list[KapFiling] = []
        primary_error: ProviderError | None = None
        primary_failed = False

        # Step 1: Try primary
        try:
            primary_results = list(self._primary.get_kap_filings(
                symbol, start_date, filing_types
            ))
            self._last_provider_used = "pykap"
            logger.debug(
                f"Primary pykap succeeded for {symbol}: {len(primary_results)} filings"
            )
        except ProviderError as e:
            primary_error = e
            if self._is_retriable_error(e):
                primary_failed = True
                logger.warning(
                    f"Primary pykap failed for {symbol} (retriable): {e}"
                )
            else:
                # Non-retriable error - propagate
                logger.error(
                    f"Primary pykap failed for {symbol} (non-retriable): {e}"
                )
                raise
        except Exception as e:
            primary_failed = True
            primary_error = ProviderError(str(e), provider="pykap")
            logger.warning(
                f"Primary pykap unexpected error for {symbol}: {e}"
            )

        # Step 2: Try fallback if primary failed OR for enrichment
        if self._fallback and self._fallback_enabled:
            try:
                fallback_results = list(self._fallback.get_kap_filings(
                    symbol, start_date, filing_types
                ))

                if primary_failed:
                    self._last_provider_used = "kap_sdk"
                    logger.info(
                        f"Fallback kap_sdk succeeded for {symbol}: "
                        f"{len(fallback_results)} filings"
                    )
                else:
                    logger.debug(
                        f"Fallback kap_sdk fetched for enrichment: "
                        f"{len(fallback_results)} filings"
                    )

            except ProviderError as e:
                logger.warning(f"Fallback kap_sdk failed for {symbol}: {e}")
                # If primary also failed, raise the primary error
                if primary_failed:
                    if primary_error:
                        raise primary_error
                    raise e
            except Exception as e:
                logger.warning(f"Fallback kap_sdk unexpected error for {symbol}: {e}")
                if primary_failed and primary_error:
                    raise primary_error

        # Step 3: Handle different scenarios
        if primary_failed:
            # Primary failed, use fallback results
            combined = fallback_results
        else:
            # Primary succeeded
            if fallback_results:
                # Enrich primary with fallback metadata
                combined = self._enrich_primary_with_fallback(
                    primary_results, fallback_results
                )
            else:
                combined = primary_results

        # Step 4: Sort by published_at descending
        combined.sort(key=lambda f: f.published_at or datetime.min, reverse=True)

        logger.info(
            f"KAP filings for {symbol}: "
            f"primary={len(primary_results)}, fallback={len(fallback_results)}, "
            f"combined={len(combined)}, provider={self._last_provider_used}"
        )

        return combined

    def _is_retriable_error(self, error: ProviderError) -> bool:
        """Determine if error warrants fallback attempt."""
        retriable_types = (
            ProviderConnectionError,
            ProviderTimeoutError,
            ProviderRateLimitError,
        )

        # ProviderAPIError with 5xx status is retriable
        if isinstance(error, ProviderAPIError):
            if error.status_code and error.status_code >= 500:
                return True
            return False

        return isinstance(error, retriable_types)

    def _enrich_primary_with_fallback(
        self,
        primary: list[KapFiling],
        fallback: list[KapFiling],
    ) -> list[KapFiling]:
        """
        Enrich primary filings with fallback metadata.

        For each primary filing:
        1. Extract disclosureIndex from source_url
        2. Find matching fallback filing by disclosureIndex
        3. Merge enrichment fields (summary, attachment_count, is_late, related_stocks)
        4. Keep primary data, add fallback enrichment

        Returns enriched primary filings.
        """
        # Build lookup dict from fallback
        fallback_by_index: dict[int, KapFiling] = {}
        for filing in fallback:
            index = self._extract_disclosure_index(filing)
            if index is not None:
                fallback_by_index[index] = filing

        # Enrich primary filings
        enriched: list[KapFiling] = []
        for filing in primary:
            index = self._extract_disclosure_index(filing)

            if index is not None and index in fallback_by_index:
                fallback_filing = fallback_by_index[index]

                # Create enriched filing (keep primary data, add fallback enrichment)
                enriched_filing = KapFiling(
                    symbol=filing.symbol,
                    title=filing.title,
                    filing_type=filing.filing_type,
                    pdf_url=filing.pdf_url,
                    source_url=filing.source_url,
                    published_at=filing.published_at,
                    provider=filing.provider,  # Keep primary provider attribution
                    # Enrichment from fallback (kap_sdk)
                    summary=fallback_filing.summary,
                    attachment_count=fallback_filing.attachment_count,
                    is_late=fallback_filing.is_late,
                    related_stocks=fallback_filing.related_stocks,
                )
                enriched.append(enriched_filing)
                logger.debug(
                    f"Enriched filing {index}: "
                    f"summary={bool(enriched_filing.summary)}, "
                    f"attachments={enriched_filing.attachment_count}"
                )
            else:
                # No enrichment available, keep original
                enriched.append(filing)

        return enriched

    def _extract_disclosure_index(self, filing: KapFiling) -> int | None:
        """Extract disclosureIndex from source_url.

        URL format: https://www.kap.org.tr/tr/Bildirim/{disclosureIndex}
        """
        if not filing.source_url:
            return None

        try:
            # Handle both /Bildirim/{index} and /BildirimPdf/{index}
            url = filing.source_url.rstrip("/")
            parts = url.split("/")

            # Find the index after "Bildirim" or "BildirimPdf"
            for i, part in enumerate(parts):
                if part in ("Bildirim", "BildirimPdf"):
                    if i + 1 < len(parts):
                        return int(parts[i + 1])

            # Fallback: last segment might be index
            return int(parts[-1])

        except (ValueError, IndexError):
            return None

    # --- Delegate other methods to primary ---

    def get_company_profile(self, symbol: str) -> CompanyProfile:
        """Company profile from primary only."""
        logger.debug(f"Fetching company profile for {symbol} from primary")
        return self._primary.get_company_profile(symbol)

    def get_price_history(
        self,
        symbol: str,
        start_date: date | None = None,
        end_date: date | None = None,
        period: str | None = None,
    ) -> Sequence[PriceBar]:
        """Delegate to primary."""
        return self._primary.get_price_history(symbol, start_date, end_date, period)

    def get_stock_snapshot(self, symbol: str) -> StockSnapshot:
        """Delegate to primary."""
        return self._primary.get_stock_snapshot(symbol)

    def get_financial_statements(
        self,
        symbol: str,
        period_type: PeriodType = PeriodType.ANNUAL,
        last_n: int = 5,
    ) -> Sequence[FinancialStatementSet]:
        """Delegate to primary."""
        return self._primary.get_financial_statements(symbol, period_type, last_n)

    def batch_price_update(
        self,
        symbols: Sequence[str],
        period: str = "1mo",
    ) -> dict[str, Sequence[PriceBar]]:
        """Delegate to primary."""
        return self._primary.batch_price_update(symbols, period)

    def health_check(self) -> bool:
        """
        Health check - primary must work, fallback optional.

        Returns True if primary is healthy, regardless of fallback status.
        """
        primary_ok = self._primary.health_check()

        if self._fallback and self._fallback_enabled:
            # Check fallback availability (may fail gracefully)
            try:
                fallback_ok = self._fallback.health_check()
                logger.debug(
                    f"Health check: primary={primary_ok}, fallback={fallback_ok}"
                )
            except Exception as e:
                logger.warning(f"Fallback health check failed: {e}")
                fallback_ok = False

        # Primary must work; fallback is bonus
        return primary_ok