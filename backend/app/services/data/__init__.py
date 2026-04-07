"""Market data provider services."""

from app.services.data.provider_models import (
    PriceBar,
    StockSnapshot,
    FinancialStatementSet,
    KapFiling,
    CompanyProfile,
    ProviderCapabilities,
    ProviderCapability,
    PeriodType,
    DataSource,
)
from app.services.data.provider_exceptions import (
    ProviderError,
    ProviderConnectionError,
    ProviderTimeoutError,
    ProviderRateLimitError,
    ProviderSymbolNotFoundError,
    ProviderDataNotFoundError,
    ProviderInvalidPeriodError,
    ProviderAPIError,
    ProviderAuthenticationError,
    ProviderPartialDataError,
    map_borsapy_exception,
)
from app.services.data.provider_interface import MarketDataProvider, BaseMarketDataProvider
from app.services.data.provider_registry import (
    ProviderRegistry,
    get_default_provider,
    get_provider_for_financials,
    get_provider_for_prices,
    get_provider_for_metrics,
    get_provider_for_kap_filings,
)
from app.services.data.providers.borsapy_provider import BorsapyProvider

__all__ = [
    # Models
    "PriceBar",
    "StockSnapshot",
    "FinancialStatementSet",
    "KapFiling",
    "CompanyProfile",
    "ProviderCapabilities",
    "ProviderCapability",
    "PeriodType",
    "DataSource",
    # Exceptions
    "ProviderError",
    "ProviderConnectionError",
    "ProviderTimeoutError",
    "ProviderRateLimitError",
    "ProviderSymbolNotFoundError",
    "ProviderDataNotFoundError",
    "ProviderInvalidPeriodError",
    "ProviderAPIError",
    "ProviderAuthenticationError",
    "ProviderPartialDataError",
    "map_borsapy_exception",
    # Interface
    "MarketDataProvider",
    "BaseMarketDataProvider",
    # Registry
    "ProviderRegistry",
    "get_default_provider",
    "get_provider_for_financials",
    "get_provider_for_prices",
    "get_provider_for_metrics",
    "get_provider_for_kap_filings",
    # Providers
    "BorsapyProvider",
]