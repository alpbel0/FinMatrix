"""Mock classes for borsapy package testing.

Provides mock implementations of borsapy.Ticker and borsapy.Tickers
for unit testing without real API calls.

Key features:
- Simple pd.DataFrame structures for price history
- NaN/Missing value scenarios for testing provider mapping
- Error injection capabilities
- Configurable data ranges
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any
from unittest.mock import MagicMock
import pandas as pd
import numpy as np


@dataclass
class MockFastInfo:
    """Mock ticker.fast_info property."""
    last_price: float = 250.50
    volume: int = 1_500_000
    market_cap: float = 15_000_000_000
    pe_ratio: float | None = 12.5
    pb_ratio: float | None = 1.8
    year_high: float = 280.00
    year_low: float = 180.00
    fifty_day_average: float | None = 245.00
    two_hundred_day_average: float | None = 220.00
    free_float: float | None = 0.45
    foreign_ratio: float | None = 0.30


@dataclass
class MockIsYatirim:
    """Mock Is Yatirim API object for financial statements."""
    financial_data: dict[str, pd.DataFrame] = field(default_factory=dict)
    _raise_on_symbol: str | None = None

    def get_financial_statements(
        self,
        symbol: str,
        statement_type: str,
        quarterly: bool,
        financial_group: str,
        last_n: int | str = "all",
    ) -> pd.DataFrame:
        """Return mock financial statement DataFrame."""
        if self._raise_on_symbol == symbol:
            raise Exception(f"Financial data not available for {symbol}")

        key = f"{symbol}_{statement_type}_{financial_group}"
        if key in self.financial_data:
            return self.financial_data[key]

        # Return default mock DataFrame
        periods = ["2024", "2023", "2022", "2021", "2020"] if not quarterly else ["2024Q3", "2024Q2", "2024Q1", "2023Q4"]
        if last_n != "all" and isinstance(last_n, int):
            periods = periods[:last_n]

        if statement_type == "balance_sheet":
            return pd.DataFrame({
                "Aktifler": [100e9, 95e9, 90e9, 85e9, 80e9],
                "Kaynaklar": [50e9, 48e9, 45e9, 42e9, 40e9],
            }, index=periods).T
        elif statement_type == "income_stmt":
            return pd.DataFrame({
                "Satışlar": [50e9, 48e9, 45e9, 42e9, 40e9],
                "Net": [5e9, 4.5e9, 4e9, 3.5e9, 3e9],
            }, index=periods).T
        elif statement_type == "cashflow":
            return pd.DataFrame({
                "Faaliyet": [6e9, 5.5e9, 5e9, 4.5e9, 4e9],
                "FCF": [4e9, 3.5e9, 3e9, 2.5e9, 2e9],
            }, index=periods).T

        return pd.DataFrame()

    def _period_sort_key(self, period: str) -> int:
        """Sort periods for financial statements."""
        # Simple sorting: earlier periods have lower values
        if "Q" in period:
            year = int(period[:4])
            q = int(period[-1])
            return year * 10 + q
        return int(period)


class MockTicker:
    """Mock borsapy.Ticker for unit testing."""

    def __init__(
        self,
        symbol: str,
        fast_info: MockFastInfo | None = None,
        info: dict[str, Any] | None = None,
        price_history: pd.DataFrame | None = None,
        news: pd.DataFrame | None = None,
        raise_on_create: bool = False,
        raise_on_history: bool = False,
        raise_on_fast_info: bool = False,
        isyatirim: MockIsYatirim | None = None,
    ):
        self.symbol = symbol.upper()
        self._fast_info = fast_info or MockFastInfo()
        self._info = info or self._default_info()
        self._price_history = price_history
        self._news = news
        self._raise_on_create = raise_on_create
        self._raise_on_history = raise_on_history
        self._raise_on_fast_info = raise_on_fast_info
        self._isyatirim = isyatirim or MockIsYatirim()

        if raise_on_create:
            raise Exception(f"Ticker creation failed for {symbol}")

    def _default_info(self) -> dict[str, Any]:
        """Default company info."""
        return {
            "longName": f"{self.symbol} Company",
            "description": f"Description for {self.symbol}",
            "sector": "Technology",
            "industry": "Software",
            "website": f"https://www.{self.symbol.lower()}.com",
            "longBusinessSummary": f"Business summary for {self.symbol}",
            "isin": f"TR{self.symbol}12345",
            "change": 5.50,
            "change_percent": 2.2,
        }

    @property
    def fast_info(self) -> MockFastInfo:
        """Return mock fast_info."""
        if self._raise_on_fast_info:
            raise Exception("fast_info access failed")
        return self._fast_info

    @property
    def info(self) -> dict[str, Any]:
        """Return mock info dict."""
        return self._info

    @property
    def news(self) -> pd.DataFrame:
        """Return mock KAP filings DataFrame."""
        if self._news is not None:
            return self._news
        # Default empty news DataFrame
        return pd.DataFrame({
            "title": ["Financial Report 2026", "Material Event Disclosure"],
            "type": ["FR", "ODA"],
            "pdf_url": ["https://kap.org.tr/api/BildirimPdf/123", "https://kap.org.tr/api/BildirimPdf/124"],
            "url": ["https://kap.org.tr/Bildirim/123", "https://kap.org.tr/Bildirim/124"],
            "published_at": [datetime(2026, 4, 8, 14, 30), datetime(2026, 4, 7, 10, 0)],
        })

    def history(
        self,
        period: str | None = None,
        start: str | None = None,
        end: str | None = None,
        interval: str = "1d",
    ) -> pd.DataFrame:
        """Return mock price history DataFrame."""
        if self._raise_on_history:
            raise Exception("History fetch failed")

        if self._price_history is not None:
            return self._price_history

        # Generate default mock DataFrame with simple structure
        return create_mock_price_dataframe(
            symbol=self.symbol,
            num_days=10,
            include_nan=False,
        )

    def _get_isyatirim(self) -> MockIsYatirim:
        """Return mock Is Yatirim API object."""
        return self._isyatirim


class MockTickers:
    """Mock borsapy.Tickers for batch operations."""

    def __init__(
        self,
        symbols: list[str],
        price_data: dict[str, pd.DataFrame] | None = None,
        raise_on_history: bool = False,
    ):
        self.symbols = [s.upper() for s in symbols]
        self._price_data = price_data or {}
        self._raise_on_history = raise_on_history

    def history(self, period: str = "1mo") -> pd.DataFrame:
        """Return mock batch price history DataFrame.

        Returns a DataFrame with MultiIndex columns (symbol, metric).
        """
        if self._raise_on_history:
            raise Exception("Batch history fetch failed")

        # Build multi-level column DataFrame
        data = {}
        for symbol in self.symbols:
            sym_df = self._price_data.get(symbol) or create_mock_price_dataframe(symbol, num_days=5)
            for col in sym_df.columns:
                data[(symbol, col)] = sym_df[col]

        dates = list(range(5))  # Simple integer index for mock
        return pd.DataFrame(data, index=dates)


def create_mock_price_dataframe(
    symbol: str = "THYAO",
    num_days: int = 10,
    start_date: date | None = None,
    include_nan: bool = False,
    nan_columns: list[str] | None = None,
    include_pd_na: bool = False,
    include_np_nan: bool = False,
    include_none: bool = False,
) -> pd.DataFrame:
    """
    Create a simple mock price history DataFrame.

    Args:
        symbol: Stock symbol (for logging)
        num_days: Number of price bars to generate
        start_date: Optional start date (defaults to 10 days ago)
        include_nan: If True, include NaN values in specified columns
        nan_columns: Columns to fill with NaN values (default: all OHLCV)
        include_pd_na: Use pd.NA for NaN values
        include_np_nan: Use np.nan for NaN values
        include_none: Use None for missing values

    Returns:
        pd.DataFrame with Open, High, Low, Close, Volume columns
    """
    if start_date is None:
        start_date = date(2026, 4, 1)

    dates = [start_date + pd.Timedelta(days=i) for i in range(num_days)]

    # Base values
    base_price = 250.0
    prices = []
    for i in range(num_days):
        day_prices = {
            "date": dates[i],
            "Open": base_price + i * 2,
            "High": base_price + i * 2 + 5,
            "Low": base_price + i * 2 - 3,
            "Close": base_price + i * 2 + 1,
            "Volume": 1_000_000 + i * 100_000,
        }
        prices.append(day_prices)

    df = pd.DataFrame(prices)
    df.set_index("date", inplace=True)

    # Add NaN/Missing values if requested
    if include_nan:
        cols_to_nan = nan_columns or ["Open", "High", "Low", "Close", "Volume"]
        for col in cols_to_nan:
            if col in df.columns:
                # Use different NaN types based on flags
                if include_pd_na:
                    df.loc[df.index[0], col] = pd.NA
                elif include_np_nan:
                    df.loc[df.index[0], col] = np.nan
                elif include_none:
                    df.loc[df.index[0], col] = None
                else:
                    df.loc[df.index[0], col] = np.nan

    return df


def create_mock_news_dataframe(
    filings: list[dict[str, Any]] | None = None,
    include_empty: bool = False,
) -> pd.DataFrame:
    """
    Create a mock KAP filings DataFrame (ticker.news).

    Args:
        filings: List of filing dicts with title, type, pdf_url, url, published_at
        include_empty: If True, return empty DataFrame

    Returns:
        pd.DataFrame with KAP filing columns
    """
    if include_empty:
        return pd.DataFrame()

    if filings is None:
        filings = [
            {
                "title": "2026 Finansal Rapor",
                "type": "FR",
                "pdf_url": "https://www.kap.org.tr/tr/api/BildirimPdf/123456",
                "url": "https://www.kap.org.tr/tr/Bildirim/123456",
                "published_at": datetime(2026, 4, 8, 14, 30, 0),
            },
            {
                "title": "Olaylara Duyarlilik Bildirimi",
                "type": "ODA",
                "pdf_url": "https://www.kap.org.tr/tr/api/BildirimPdf/123457",
                "url": "https://www.kap.org.tr/tr/Bildirim/123457",
                "published_at": datetime(2026, 4, 7, 10, 0, 0),
            },
        ]

    return pd.DataFrame(filings)


def create_mock_financial_dataframe(
    statement_type: str = "balance_sheet",
    periods: list[str] | None = None,
    include_nan: bool = False,
    financial_group: str = "XI_29",
) -> pd.DataFrame:
    """
    Create a mock financial statement DataFrame.

    Args:
        statement_type: "balance_sheet", "income_stmt", or "cashflow"
        periods: List of period strings (e.g., ["2024", "2023"])
        include_nan: If True, include NaN values in some cells
        financial_group: "XI_29" or "UFRS" (affects row names)

    Returns:
        pd.DataFrame with financial data
    """
    if periods is None:
        periods = ["2024", "2023", "2022", "2021", "2020"]

    if statement_type == "balance_sheet":
        data = {
            "Aktifler": [100e9, 95e9, 90e9, 85e9, 80e9],
            "Kaynaklar": [50e9, 48e9, 45e9, 42e9, 40e9],
            "Nakit": [10e9, 9e9, 8e9, 7e9, 6e9],
        }
    elif statement_type == "income_stmt":
        data = {
            "Satışlar": [50e9, 48e9, 45e9, 42e9, 40e9],
            "Net": [5e9, 4.5e9, 4e9, 3.5e9, 3e9],
            "Giderler": [40e9, 38e9, 36e9, 34e9, 32e9],
        }
    elif statement_type == "cashflow":
        data = {
            "Faaliyet": [6e9, 5.5e9, 5e9, 4.5e9, 4e9],
            "FCF": [4e9, 3.5e9, 3e9, 2.5e9, 2e9],
            "Yatırım": [-2e9, -1.8e9, -1.5e9, -1.2e9, -1e9],
        }
    else:
        data = {"Unknown": [0] * len(periods)}

    df = pd.DataFrame(data, index=periods).T

    if include_nan:
        # Add NaN to first cell
        df.iloc[0, 0] = np.nan

    return df


# Error injection helpers

def create_ticker_that_raises(symbol: str, error_type: str = "connection") -> MockTicker:
    """
    Create a MockTicker configured to raise specific errors.

    Args:
        symbol: Stock symbol
        error_type: "connection", "timeout", "symbol_not_found", "create"

    Returns:
        MockTicker configured to raise the specified error
    """
    error_map = {
        "connection": ConnectionError(f"Connection failed for {symbol}"),
        "timeout": TimeoutError(f"Request timed out for {symbol}"),
        "symbol_not_found": ValueError(f"Symbol {symbol} not found"),
        "create": Exception(f"Ticker creation failed for {symbol}"),
    }

    exc = error_map.get(error_type, Exception(f"Unknown error for {symbol}"))

    if error_type == "create":
        return MockTicker(symbol, raise_on_create=True)

    ticker = MockTicker(symbol)

    if error_type == "connection":
        ticker._raise_on_history = True
    elif error_type == "timeout":
        ticker._raise_on_history = True

    return ticker