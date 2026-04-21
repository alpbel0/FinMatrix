"""Borsapy market data provider implementation."""

import sys
import unicodedata
from collections.abc import Sequence
from datetime import date, datetime
from pathlib import Path

import pandas as pd

# Add borsapy to path (it's in search/borsapy)
borsapy_path = Path(__file__).parent.parent.parent.parent.parent.parent / "search" / "borsapy"
if borsapy_path.exists():
    sys.path.insert(0, str(borsapy_path.parent))

import borsapy as bp

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
    ProviderError,
    map_borsapy_exception,
)
from app.services.utils.logging import logger


class BorsapyProvider(BaseMarketDataProvider):
    """
    Borsapy-based market data provider for BIST stocks.

    Uses borsapy v0.8.4 for:
    - Price history (via TradingView WebSocket)
    - Financial statements (via Is Yatirim API)
    - Company metrics (via Is Yatirim API)
    - KAP filings (via KAP API)

    Key features:
    - Supports intraday data (1m, 5m, 15m, 30m, 1h, 4h)
    - Supports quarterly and annual financials
    - Handles UFRS (banks) and XI_29 (non-banks) financial formats
    """

    REVENUE_LABELS = (
        "Satış Gelirleri",
        "Hasılat",
        "Faiz Gelirleri",
    )
    NET_INCOME_LABELS = (
        "Ana Ortaklık Payları",
        "Net Dönem Karı/Zararı",
        "NET DÖNEM KARI/ZARARI",
        "XXIII. NET DÖNEM KARI/ZARARI (XVII+XXII)",
        "23.1 Grubun Karı/Zararı",
        "DÖNEM KARI (ZARARI)",
        "SÜRDÜRÜLEN FAALİYETLER DÖNEM KARI/ZARARI",
    )

    def __init__(self, timeout: float = 30.0, retry_count: int = 3):
        super().__init__(timeout=timeout, retry_count=retry_count)
        logger.info("Initializing BorsapyProvider")

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supported_data={
                ProviderCapability.PRICE_HISTORY,
                ProviderCapability.METRICS,
                ProviderCapability.FINANCIALS,
                ProviderCapability.KAP_FILINGS,
                ProviderCapability.COMPANY_PROFILE,
            },
            supported_markets={"BIST"},
            max_history_days=3650,  # ~10 years from TradingView
            supports_intraday=True,  # 1m, 5m, 15m, 30m, 1h, 4h
            supports_quarterly_financials=True,
            timeout_seconds=self._timeout,
            retry_count=self._retry_count,
        )

    def _create_ticker(self, symbol: str) -> bp.Ticker:
        """Create borsapy Ticker instance with error handling."""
        try:
            ticker = bp.Ticker(symbol.upper())
            return ticker
        except Exception as exc:
            # Try to map known exceptions
            mapped_exc = map_borsapy_exception(exc)
            logger.error(f"Failed to create ticker for {symbol}: {mapped_exc}")
            raise mapped_exc

    def get_price_history(
        self,
        symbol: str,
        start_date: date | None = None,
        end_date: date | None = None,
        period: str | None = None,
    ) -> Sequence[PriceBar]:
        """
        Fetch historical OHLCV data using borsapy.

        Args:
            symbol: BIST stock symbol (THYAO, GARAN, etc.)
            start_date: Optional start date for date range query
            end_date: Optional end date for date range query
            period: Predefined period ("1mo", "1y", "max", etc.)

        Returns:
            List of PriceBar objects with OHLCV data

        Note:
            If period is specified, it overrides start_date/end_date.
            For intraday data, use interval parameter (future enhancement).
        """
        logger.debug(f"Fetching price history for {symbol}")

        ticker = self._create_ticker(symbol)

        try:
            # Use period if specified, otherwise use date range
            if period:
                df = ticker.history(period=period)
            elif start_date or end_date:
                start_str = start_date.isoformat() if start_date else None
                end_str = end_date.isoformat() if end_date else None
                # borsapy history() uses start/end for date range
                df = ticker.history(start=start_str, end=end_str, period="max")
            else:
                # Default to 1 year if nothing specified
                df = ticker.history(period="1y")

            if df.empty:
                logger.warning(f"No price data found for {symbol}")
                return []

            # Convert DataFrame to PriceBar sequence
            bars = []
            for idx, row in df.iterrows():
                # Handle different index types
                if hasattr(idx, 'date'):
                    bar_date = idx.date()
                elif isinstance(idx, str):
                    bar_date = date.fromisoformat(idx[:10])
                else:
                    bar_date = idx

                bar = PriceBar(
                    date=bar_date,
                    open=row.get("Open") if "Open" in df.columns else None,
                    high=row.get("High") if "High" in df.columns else None,
                    low=row.get("Low") if "Low" in df.columns else None,
                    close=row.get("Close") if "Close" in df.columns else None,
                    volume=row.get("Volume") if "Volume" in df.columns else None,
                    adjusted_close=row.get("Close"),  # TradingView returns adjusted
                    source=DataSource.BORSAPY,
                )
                bars.append(bar)

            logger.info(f"Fetched {len(bars)} price bars for {symbol}")
            return bars

        except Exception as exc:
            logger.error(f"Error fetching prices for {symbol}: {exc}")
            if isinstance(exc, ProviderError):
                raise
            raise map_borsapy_exception(exc)

    def get_stock_snapshot(self, symbol: str) -> StockSnapshot:
        """
        Fetch current stock metrics and basic info.

        Uses borsapy's fast_info for quick access to key metrics
        and info for additional details like change percentages.
        """
        logger.debug(f"Fetching snapshot for {symbol}")

        ticker = self._create_ticker(symbol)

        try:
            fast_info = ticker.fast_info
            info = ticker.info

            snapshot = StockSnapshot(
                symbol=symbol.upper(),
                last_price=self._safe_attr(fast_info, "last_price"),
                change=info.get("change"),
                change_percent=info.get("change_percent"),
                volume=self._safe_attr(fast_info, "volume"),
                market_cap=self._safe_attr(fast_info, "market_cap"),
                pe_ratio=self._first_non_null(
                    self._safe_attr(fast_info, "pe_ratio"),
                    info.get("pe_ratio"),
                    info.get("trailingPE"),
                ),
                pb_ratio=self._first_non_null(
                    self._safe_attr(fast_info, "pb_ratio"),
                    info.get("pb_ratio"),
                    info.get("priceToBook"),
                ),
                dividend_yield=self._first_non_null(
                    info.get("dividend_yield"),
                    info.get("dividendYield"),
                ),
                trailing_eps=self._first_non_null(
                    info.get("trailing_eps"),
                    info.get("trailingEps"),
                    info.get("eps"),
                ),
                roe=self._first_non_null(
                    info.get("roe"),
                    info.get("returnOnEquity"),
                ),
                debt_equity=self._first_non_null(
                    info.get("debt_equity"),
                    info.get("debtToEquity"),
                    info.get("debt_to_equity"),
                ),
                year_high=self._safe_attr(fast_info, "year_high"),
                year_low=self._safe_attr(fast_info, "year_low"),
                fifty_day_avg=self._safe_attr(fast_info, "fifty_day_average"),
                two_hundred_day_avg=self._safe_attr(fast_info, "two_hundred_day_average"),
                free_float=self._first_non_null(
                    self._safe_attr(fast_info, "free_float"),
                    info.get("free_float"),
                    info.get("floatSharesPercent"),
                ),
                foreign_ratio=self._first_non_null(
                    self._safe_attr(fast_info, "foreign_ratio"),
                    info.get("foreign_ratio"),
                    info.get("foreignOwnership"),
                ),
                source=DataSource.BORSAPY,
            )

            logger.debug(f"Snapshot fetched for {symbol}: last_price={snapshot.last_price}")
            return snapshot

        except Exception as exc:
            logger.error(f"Error fetching snapshot for {symbol}: {exc}")
            if isinstance(exc, ProviderError):
                raise
            raise map_borsapy_exception(exc)

    def get_financial_statements(
        self,
        symbol: str,
        period_type: PeriodType = PeriodType.ANNUAL,
        last_n: int = 5,
    ) -> Sequence[FinancialStatementSet]:
        """
        Fetch financial statements from Is Yatirim via borsapy.

        Args:
            symbol: BIST stock symbol
            period_type: ANNUAL or QUARTERLY
            last_n: Number of periods to fetch (default 5)

        Returns:
            List of FinancialStatementSet objects

        Note:
            - Bank stocks use UFRS financial format
            - Non-bank stocks use XI_29 format
            - Financial statement item names are in Turkish
        """
        logger.debug(f"Fetching financials for {symbol}, period={period_type.value}")

        ticker = self._create_ticker(symbol)
        quarterly = period_type == PeriodType.QUARTERLY

        try:
            info = ticker.info
            sector = info.get("sector", "")
            preferred_group, fallback_groups = self._resolve_financial_groups(sector)

            logger.debug(
                "%s sector=%s preferred financial_group=%s fallbacks=%s",
                symbol,
                sector,
                preferred_group,
                fallback_groups,
            )

            balance_df, income_df, cashflow_df = self._fetch_financial_dataframes(
                ticker=ticker,
                symbol=symbol,
                quarterly=quarterly,
                last_n=last_n,
                preferred_group=preferred_group,
                fallback_groups=fallback_groups,
            )

            # Extract periods from DataFrame columns
            periods = (
                self._extract_periods(balance_df.columns)
                or self._extract_periods(income_df.columns)
                or self._extract_periods(cashflow_df.columns)
            )
            if not periods:
                raise ValueError(f"No financial statement periods available for {symbol}")

            statements = []
            for period_str in periods:
                stmt_date = self._parse_period_to_date(period_str, period_type)

                # Extract values from DataFrames
                # Note: Item names in Turkish, may vary between UFRS/XI_29
                stmt = FinancialStatementSet(
                    symbol=symbol.upper(),
                    period_type=period_type,
                    statement_date=stmt_date,
                    source=DataSource.BORSAPY,
                    # Balance Sheet items
                    total_assets=self._get_value(balance_df, "Aktifler", period_str),
                    total_equity=self._get_value(balance_df, "Kaynaklar", period_str),
                    # Income Statement items
                    revenue=self._get_first_available_value(
                        income_df,
                        self.REVENUE_LABELS,
                        period_str,
                    ),
                    net_income=self._get_first_available_value(
                        income_df,
                        self.NET_INCOME_LABELS,
                        period_str,
                    ),
                    # Cash Flow items
                    operating_cash_flow=self._get_value(cashflow_df, "Faaliyet", period_str),
                    free_cash_flow=self._get_value(cashflow_df, "FCF", period_str),
                )
                statements.append(stmt)

            logger.info(f"Fetched {len(statements)} financial statements for {symbol}")
            return statements

        except Exception as exc:
            logger.error(f"Error fetching financials for {symbol}: {exc}")
            if isinstance(exc, ProviderError):
                raise
            raise map_borsapy_exception(exc)

    def _fetch_financial_dataframes(
        self,
        ticker,
        symbol: str,
        quarterly: bool,
        last_n: int,
        preferred_group: str,
        fallback_groups: Sequence[str],
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Fetch financial statement DataFrames with group fallback and partial-data tolerance."""
        isyatirim = ticker._get_isyatirim()
        balance_df = self._fetch_statement_with_fallback(
            isyatirim=isyatirim,
            symbol=symbol,
            statement_type="balance_sheet",
            quarterly=quarterly,
            last_n=last_n,
            preferred_group=preferred_group,
            fallback_groups=fallback_groups,
            required=True,
        )
        income_df = self._fetch_statement_with_fallback(
            isyatirim=isyatirim,
            symbol=symbol,
            statement_type="income_stmt",
            quarterly=quarterly,
            last_n=last_n,
            preferred_group=preferred_group,
            fallback_groups=fallback_groups,
            required=True,
        )
        cashflow_df = self._fetch_statement_with_fallback(
            isyatirim=isyatirim,
            symbol=symbol,
            statement_type="cashflow",
            quarterly=quarterly,
            last_n=last_n,
            preferred_group=preferred_group,
            fallback_groups=fallback_groups,
            required=False,
        )
        return balance_df, income_df, cashflow_df

    def _fetch_statement_with_fallback(
        self,
        isyatirim,
        symbol: str,
        statement_type: str,
        quarterly: bool,
        last_n: int,
        preferred_group: str,
        fallback_groups: Sequence[str],
        required: bool,
    ) -> pd.DataFrame:
        """Fetch a single statement type, trying financial groups in order."""
        groups_to_try = [preferred_group, *fallback_groups]
        last_error: Exception | None = None

        for group in groups_to_try:
            try:
                return self._fetch_statement_frame(
                    isyatirim=isyatirim,
                    symbol=symbol,
                    statement_type=statement_type,
                    quarterly=quarterly,
                    financial_group=group,
                    last_n=last_n,
                )
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "%s fetch failed for %s with group %s: %s",
                    statement_type,
                    symbol,
                    group,
                    exc,
                )

        if required and last_error is not None:
            raise last_error

        return pd.DataFrame()

    def _fetch_statement_frame(
        self,
        isyatirim,
        symbol: str,
        statement_type: str,
        quarterly: bool,
        financial_group: str,
        last_n: int,
    ) -> pd.DataFrame:
        """
        Fetch statement data from Is Yatirim and trim to the requested periods.

        `last_n='all'` is more resilient because the provider skips empty leading batches,
        while narrow annual requests can fail entirely when the latest annual period is not published yet.
        """
        df = isyatirim.get_financial_statements(
            symbol=symbol,
            statement_type=statement_type,
            quarterly=quarterly,
            financial_group=financial_group,
            last_n="all",
        )
        if df.empty:
            return df

        sorted_columns = sorted(df.columns, key=isyatirim._period_sort_key, reverse=True)
        trimmed_columns = sorted_columns[:last_n]
        return df[trimmed_columns]

    def _resolve_financial_groups(self, sector: str | None) -> tuple[str, list[str]]:
        """Pick the most likely financial group and a fallback based on sector metadata."""
        normalized_sector = self._normalize_text(sector or "")
        bank_markers = ("bank", "banka", "mali kurulus", "financial")
        is_bank = any(marker in normalized_sector for marker in bank_markers)

        if is_bank:
            return "UFRS", ["XI_29"]
        return "XI_29", ["UFRS"]

    def _normalize_text(self, value: str) -> str:
        """Normalize Turkish text for keyword matching."""
        normalized = unicodedata.normalize("NFKD", value)
        ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
        return ascii_only.lower().strip()

    def get_company_profile(self, symbol: str) -> CompanyProfile:
        """Fetch company metadata and basic info."""
        logger.debug(f"Fetching company profile for {symbol}")

        ticker = self._create_ticker(symbol)

        try:
            info = ticker.info

            profile = CompanyProfile(
                symbol=symbol.upper(),
                company_name=info.get("longName") or info.get("description"),
                sector=info.get("sector"),
                industry=info.get("industry"),
                website=info.get("website"),
                description=info.get("longBusinessSummary"),
                isin=info.get("isin"),
                exchange="BIST",
                source=DataSource.BORSAPY,
            )

            logger.debug(f"Profile fetched for {symbol}: name={profile.company_name}")
            return profile

        except Exception as exc:
            logger.error(f"Error fetching profile for {symbol}: {exc}")
            if isinstance(exc, ProviderError):
                raise
            raise map_borsapy_exception(exc)

    def get_kap_filings(
        self,
        symbol: str,
        start_date: date | None = None,
        filing_types: Sequence[str] | None = None,
    ) -> Sequence[KapFiling]:
        """
        Fetch KAP (Public Disclosure Platform) filings.

        Args:
            symbol: BIST stock symbol
            start_date: Optional filter for filings after this date
            filing_types: Optional filter for specific filing types

        Returns:
            List of KapFiling objects
        """
        logger.debug(f"Fetching KAP filings for {symbol}")

        ticker = self._create_ticker(symbol)

        try:
            # borsapy news property returns KAP disclosures
            news_df = ticker.news

            if news_df.empty:
                logger.warning(f"No KAP filings found for {symbol}")
                return []

            filings = []
            for _, row in news_df.iterrows():
                # Filter by start_date if specified
                if start_date:
                    published = row.get("published_at")
                    if published:
                        if isinstance(published, str):
                            pub_date = date.fromisoformat(published[:10])
                        elif isinstance(published, datetime):
                            pub_date = published.date()
                        else:
                            pub_date = published

                        if pub_date < start_date:
                            continue

                filing = KapFiling(
                    symbol=symbol.upper(),
                    title=row.get("title", ""),
                    filing_type=row.get("type"),
                    pdf_url=row.get("pdf_url"),
                    source_url=row.get("url"),
                    published_at=row.get("published_at"),
                    provider=DataSource.BORSAPY,
                )

                # Filter by filing_types if specified
                if filing_types and filing.filing_type:
                    if filing.filing_type not in filing_types:
                        continue

                filings.append(filing)

            logger.info(f"Fetched {len(filings)} KAP filings for {symbol}")
            return filings

        except Exception as exc:
            logger.error(f"Error fetching KAP filings for {symbol}: {exc}")
            if isinstance(exc, ProviderError):
                raise
            raise map_borsapy_exception(exc)

    def batch_price_update(
        self,
        symbols: Sequence[str],
        period: str = "1mo",
    ) -> dict[str, Sequence[PriceBar]]:
        """
        Batch fetch price history for multiple symbols.

        Uses borsapy's Tickers class for efficient batch downloading.

        Args:
            symbols: List of BIST stock symbols
            period: Period for history ("1mo", "1y", etc.)

        Returns:
            Dictionary mapping symbol to list of PriceBar objects
        """
        logger.info(f"Batch price update for {len(symbols)} symbols")

        try:
            # Use borsapy's Tickers for batch download
            symbols_list = [s.upper() for s in symbols]
            tickers = bp.Tickers(symbols_list)
            df = tickers.history(period=period)

            # Group by symbol
            results = {}
            for symbol in symbols_list:
                try:
                    # Check if symbol exists in DataFrame columns
                    if symbol in df.columns.get_level_values(0):
                        sym_df = df[symbol]
                        bars = []

                        for idx, row in sym_df.iterrows():
                            if hasattr(idx, 'date'):
                                bar_date = idx.date()
                            elif isinstance(idx, str):
                                bar_date = date.fromisoformat(idx[:10])
                            else:
                                bar_date = idx

                            bar = PriceBar(
                                date=bar_date,
                                open=row.get("Open") if "Open" in sym_df.columns else None,
                                high=row.get("High") if "High" in sym_df.columns else None,
                                low=row.get("Low") if "Low" in sym_df.columns else None,
                                close=row.get("Close") if "Close" in sym_df.columns else None,
                                volume=row.get("Volume") if "Volume" in sym_df.columns else None,
                                source=DataSource.BORSAPY,
                            )
                            bars.append(bar)

                        results[symbol] = bars
                    else:
                        logger.warning(f"Symbol {symbol} not found in batch results")
                        results[symbol] = []
                except Exception as e:
                    logger.warning(f"Error processing {symbol} in batch: {e}")
                    results[symbol] = []

            successful = [s for s in symbols_list if len(results.get(s, [])) > 0]
            logger.info(f"Batch update: {len(successful)}/{len(symbols)} symbols successful")
            return results

        except Exception as exc:
            logger.error(f"Error in batch price update: {exc}")
            raise map_borsapy_exception(exc)

    def health_check(self) -> bool:
        """Verify borsapy provider is operational."""
        try:
            # Quick test with a well-known symbol
            ticker = bp.Ticker("THYAO")
            _ = ticker.fast_info.last_price
            logger.debug("Health check passed")
            return True
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            return False

    # --- Helper Methods ---

    def _extract_periods(self, columns) -> list[str]:
        """
        Extract period strings from DataFrame columns.

        Financial statement columns are typically:
        - Annual: "2024", "2023", "2022"
        - Quarterly: "2024Q3", "2024Q2", "2024Q1"
        """
        periods = []
        for col in columns:
            col_str = str(col)
            # Check for year pattern (annual)
            if col_str.isdigit() and len(col_str) == 4:
                periods.append(col_str)
            # Check for quarter pattern (quarterly)
            elif "Q" in col_str and col_str[:4].isdigit():
                periods.append(col_str)

        # Sort descending (most recent first)
        return sorted(periods, reverse=True)

    def _safe_attr(self, obj, attr_name: str):
        """Return provider attribute when present, otherwise None."""
        return getattr(obj, attr_name, None)

    def _first_non_null(self, *values):
        """Return first non-null value from a list of candidates."""
        for value in values:
            if value is not None:
                return value
        return None

    def _parse_period_to_date(self, period: str, period_type: PeriodType) -> date:
        """
        Convert period string to statement date.

        Annual "2024" -> 2024-12-31
        Quarterly "2024Q3" -> 2024-09-30
        """
        if period_type == PeriodType.QUARTERLY:
            # Format: "2024Q3"
            year = int(period[:4])
            q = int(period[-1])
            # Quarter end months: Q1=3, Q2=6, Q3=9, Q4=12
            month_end = q * 3
            # Last day of quarter month
            if month_end in [6, 9]:
                day = 30
            else:
                day = 31
            return date(year, month_end, day)
        else:
            # Annual: "2024" -> year end
            return date(int(period), 12, 31)

    def _get_value(
        self,
        df: pd.DataFrame,
        row_pattern: str,
        period: str
    ) -> float | None:
        """
        Extract value from financial statement DataFrame.

        Args:
            df: Financial statement DataFrame
            row_pattern: Pattern to match row index (partial match)
            period: Column name (e.g., "2024", "2024Q3")

        Returns:
            Numeric value or None if not found
        """
        try:
            # Find row matching pattern
            matching_rows = df[df.index.astype(str).str.contains(row_pattern, case=False, na=False)]

            if matching_rows.empty:
                return None

            # Get first matching row's value for the period
            if period in df.columns:
                val = matching_rows[period].iloc[0]
                if pd.notna(val):
                    return float(val)

        except Exception as e:
            logger.debug(f"Could not extract value for '{row_pattern}' in period {period}: {e}")

        return None

    def _get_first_available_value(
        self,
        df: pd.DataFrame,
        row_labels: Sequence[str],
        period: str,
    ) -> float | None:
        """Extract the first populated metric using exact row-label priority."""
        if df.empty or period not in df.columns:
            return None

        label_to_index = {
            self._normalize_financial_label(index_label): index_label
            for index_label in df.index
        }

        for row_label in row_labels:
            normalized_label = self._normalize_financial_label(row_label)
            index_label = label_to_index.get(normalized_label)
            if index_label is None:
                continue

            value = df.at[index_label, period]
            if pd.notna(value):
                return float(value)

        return None

    def _normalize_financial_label(self, label: object) -> str:
        """Normalize a financial statement row label for exact comparisons."""
        return " ".join(str(label).casefold().split())
