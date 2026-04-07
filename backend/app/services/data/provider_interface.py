"""Provider protocol/interface for market data abstraction."""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import date, datetime
from typing import Protocol, runtime_checkable, Any

from app.services.data.provider_models import (
    CompanyProfile,
    FinancialStatementSet,
    KapFiling,
    PeriodType,
    PriceBar,
    ProviderCapabilities,
    StockSnapshot,
)


@runtime_checkable
class MarketDataProvider(Protocol):
    """
    Protocol defining the contract for market data providers.

    Application code interacts only with this interface,
    never with provider implementation details.
    """

    @property
    def capabilities(self) -> ProviderCapabilities:
        """Return provider's supported capabilities."""
        ...

    def get_price_history(
        self,
        symbol: str,
        start_date: date | None = None,
        end_date: date | None = None,
        period: str | None = None,  # "1mo", "1y", "max", etc.
    ) -> Sequence[PriceBar]:
        """Fetch historical OHLCV data for a single stock."""
        ...

    def get_stock_snapshot(self, symbol: str) -> StockSnapshot:
        """Fetch current metrics and basic info."""
        ...

    def get_financial_statements(
        self,
        symbol: str,
        period_type: PeriodType = PeriodType.ANNUAL,
        last_n: int = 5,
    ) -> Sequence[FinancialStatementSet]:
        """Fetch financial statements (balance sheet, income, cash flow)."""
        ...

    def get_company_profile(self, symbol: str) -> CompanyProfile:
        """Fetch company metadata."""
        ...

    def get_kap_filings(
        self,
        symbol: str,
        start_date: date | None = None,
        filing_types: Sequence[str] | None = None,
    ) -> Sequence[KapFiling]:
        """Fetch KAP disclosures for a stock."""
        ...

    def batch_price_update(
        self,
        symbols: Sequence[str],
        period: str = "1mo",
    ) -> dict[str, Sequence[PriceBar]]:
        """Fetch price history for multiple stocks."""
        ...

    def health_check(self) -> bool:
        """Check if provider is operational."""
        ...


class BaseMarketDataProvider(ABC):
    """
    Abstract base class providing shared infrastructure.

    Concrete providers inherit from this and implement
    abstract methods. Provides retry logic and common helpers.
    """

    def __init__(self, timeout: float = 30.0, retry_count: int = 3):
        self._timeout = timeout
        self._retry_count = retry_count

    @property
    @abstractmethod
    def capabilities(self) -> ProviderCapabilities:
        """Return provider's supported capabilities."""
        pass

    def _with_retry(self, operation: callable, *args, **kwargs) -> Any:
        """Execute operation with retry logic."""
        from app.services.data.provider_exceptions import ProviderTimeoutError
        import time

        for attempt in range(self._retry_count):
            try:
                return operation(*args, **kwargs)
            except ProviderTimeoutError:
                if attempt < self._retry_count - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                raise
        raise RuntimeError("Unexpected retry exhaustion")

    @abstractmethod
    def get_price_history(
        self,
        symbol: str,
        start_date: date | None = None,
        end_date: date | None = None,
        period: str | None = None,
    ) -> Sequence[PriceBar]:
        pass

    @abstractmethod
    def get_stock_snapshot(self, symbol: str) -> StockSnapshot:
        pass

    @abstractmethod
    def get_financial_statements(
        self,
        symbol: str,
        period_type: PeriodType = PeriodType.ANNUAL,
        last_n: int = 5,
    ) -> Sequence[FinancialStatementSet]:
        pass

    @abstractmethod
    def get_company_profile(self, symbol: str) -> CompanyProfile:
        pass

    @abstractmethod
    def get_kap_filings(
        self,
        symbol: str,
        start_date: date | None = None,
        filing_types: Sequence[str] | None = None,
    ) -> Sequence[KapFiling]:
        pass

    @abstractmethod
    def batch_price_update(
        self,
        symbols: Sequence[str],
        period: str = "1mo",
    ) -> dict[str, Sequence[PriceBar]]:
        pass

    @abstractmethod
    def health_check(self) -> bool:
        pass