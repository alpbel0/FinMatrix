"""Provider registry for capability-based provider selection."""

from functools import lru_cache

from app.services.data.provider_interface import MarketDataProvider
from app.services.data.provider_models import ProviderCapability
from app.services.utils.logging import logger


class ProviderRegistry:
    """
    Registry for market data providers.

    Enables capability-based selection - application code
    requests a provider for specific capabilities without
    knowing the implementation.
    """

    _providers: dict[str, MarketDataProvider] = {}
    _initialized: bool = False

    @classmethod
    def initialize(cls) -> None:
        """Initialize registry with default providers."""
        if cls._initialized:
            return

        # Import and register Borsapy provider
        try:
            from app.services.data.providers.borsapy_provider import BorsapyProvider
            cls.register("borsapy", BorsapyProvider())
            logger.info("ProviderRegistry initialized with borsapy provider")
        except ImportError as e:
            logger.warning(f"Could not import BorsapyProvider: {e}")

        # Import and register Pykap provider (KAP disclosures)
        try:
            from app.services.data.providers.pykap_provider import PykapProvider
            cls.register("pykap", PykapProvider())
            logger.info("ProviderRegistry initialized with pykap provider")
        except ImportError as e:
            logger.warning(f"Could not import PykapProvider: {e}")

        cls._initialized = True

    @classmethod
    def register(cls, name: str, provider: MarketDataProvider) -> None:
        """Register a provider by name."""
        cls._providers[name] = provider
        logger.debug(f"Registered provider: {name}")

    @classmethod
    def get_provider(cls, name: str = "borsapy") -> MarketDataProvider:
        """Get provider by name."""
        cls.initialize()

        if name not in cls._providers:
            raise ValueError(f"Provider '{name}' not registered")

        return cls._providers[name]

    @classmethod
    def get_provider_for_capability(
        cls,
        capability: ProviderCapability,
        market: str = "BIST",
    ) -> MarketDataProvider:
        """
        Get a provider that supports a specific capability.

        Selection priority:
        1. Provider explicitly marked as preferred for capability
        2. First provider that supports the capability
        3. Default provider (borsapy)
        """
        cls.initialize()

        # Find providers with the capability
        candidates = []
        for name, provider in cls._providers.items():
            caps = provider.capabilities
            if capability in caps.supported_data and market in caps.supported_markets:
                candidates.append((name, provider))

        if not candidates:
            raise ValueError(
                f"No provider supports {capability} for market {market}"
            )

        # Return first candidate (could be enhanced with priority logic)
        logger.debug(f"Selected provider '{candidates[0][0]}' for capability {capability}")
        return candidates[0][1]

    @classmethod
    def list_providers(cls) -> list[str]:
        """List all registered provider names."""
        cls.initialize()
        return list(cls._providers.keys())

    @classmethod
    def get_capabilities(cls, name: str = "borsapy") -> "ProviderCapabilities":
        """Get capabilities of a specific provider."""
        return cls.get_provider(name).capabilities


# Convenience functions with caching


@lru_cache
def get_default_provider() -> MarketDataProvider:
    """Get the default market data provider (cached)."""
    return ProviderRegistry.get_provider("borsapy")


def get_provider_for_financials() -> MarketDataProvider:
    """Get provider for financial statements."""
    return ProviderRegistry.get_provider_for_capability(
        ProviderCapability.FINANCIALS
    )


def get_provider_for_prices() -> MarketDataProvider:
    """Get provider for price history."""
    return ProviderRegistry.get_provider_for_capability(
        ProviderCapability.PRICE_HISTORY
    )


def get_provider_for_metrics() -> MarketDataProvider:
    """Get provider for stock metrics."""
    return ProviderRegistry.get_provider_for_capability(
        ProviderCapability.METRICS
    )


def get_provider_for_kap_filings() -> MarketDataProvider:
    """Get provider for KAP filings."""
    return ProviderRegistry.get_provider_for_capability(
        ProviderCapability.KAP_FILINGS
    )