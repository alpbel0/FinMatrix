"""Unit tests for ProviderRegistry.

Tests provider registration, capability-based selection,
convenience functions, and fallback provider behavior.
"""

import pytest
from unittest.mock import MagicMock, patch

from app.services.data.provider_models import (
    ProviderCapabilities,
    ProviderCapability,
    DataSource,
)
from app.services.data.provider_registry import (
    ProviderRegistry,
    get_default_provider,
    get_provider_for_financials,
    get_provider_for_prices,
    get_provider_for_metrics,
    get_provider_for_kap_filings,
)


def create_mock_provider(
    name: str = "test_provider",
    supported_data: set[ProviderCapability] | None = None,
    supported_markets: set[str] | None = None,
) -> MagicMock:
    """Create a mock provider with configurable capabilities."""
    provider = MagicMock()
    provider.name = name

    if supported_data is None:
        supported_data = {ProviderCapability.PRICE_HISTORY}
    if supported_markets is None:
        supported_markets = {"BIST"}

    provider.capabilities = ProviderCapabilities(
        supported_data=supported_data,
        supported_markets=supported_markets,
    )

    return provider


@pytest.fixture(autouse=True)
def reset_registry():
    """Reset the registry before and after each test."""
    # Clear before test
    ProviderRegistry._providers = {}
    ProviderRegistry._initialized = False

    # Clear LRU cache
    get_default_provider.cache_clear()

    yield

    # Clear after test
    ProviderRegistry._providers = {}
    ProviderRegistry._initialized = False
    get_default_provider.cache_clear()


def _prevent_auto_initialize():
    """Helper to prevent auto-initialization during tests."""
    ProviderRegistry._initialized = True  # Prevent initialize() from running


class TestProviderRegistration:
    """Tests for provider registration."""

    def test_register_provider(self):
        """Should register a provider by name."""
        provider = create_mock_provider("test_provider")

        ProviderRegistry.register("test", provider)

        assert "test" in ProviderRegistry._providers
        assert ProviderRegistry._providers["test"] == provider

    def test_register_overwrites_existing(self):
        """Should overwrite existing provider with same name."""
        provider1 = create_mock_provider("provider1")
        provider2 = create_mock_provider("provider2")

        ProviderRegistry.register("test", provider1)
        ProviderRegistry.register("test", provider2)

        assert ProviderRegistry._providers["test"] == provider2

    def test_get_provider_returns_registered(self):
        """Should return registered provider by name."""
        _prevent_auto_initialize()
        provider = create_mock_provider("test_provider")
        ProviderRegistry.register("test", provider)

        result = ProviderRegistry.get_provider("test")

        assert result == provider

    def test_get_provider_raises_for_unknown(self):
        """Should raise ValueError for unregistered provider."""
        _prevent_auto_initialize()
        with pytest.raises(ValueError) as exc_info:
            ProviderRegistry.get_provider("unknown")

        assert "not registered" in str(exc_info.value)

    def test_list_providers_returns_names(self):
        """Should return list of registered provider names."""
        _prevent_auto_initialize()
        ProviderRegistry.register("borsapy", create_mock_provider())
        ProviderRegistry.register("pykap", create_mock_provider())

        names = ProviderRegistry.list_providers()

        assert "borsapy" in names
        assert "pykap" in names
        assert len(names) == 2


class TestCapabilityBasedSelection:
    """Tests for capability-based provider selection."""

    def test_get_provider_for_capability(self):
        """Should return provider that supports the capability."""
        _prevent_auto_initialize()
        provider = create_mock_provider(
            supported_data={ProviderCapability.PRICE_HISTORY}
        )
        ProviderRegistry.register("test", provider)

        result = ProviderRegistry.get_provider_for_capability(
            ProviderCapability.PRICE_HISTORY
        )

        assert result == provider

    def test_get_provider_for_capability_market_filter(self):
        """Should filter providers by market."""
        _prevent_auto_initialize()
        provider_bist = create_mock_provider(
            supported_data={ProviderCapability.PRICE_HISTORY},
            supported_markets={"BIST"},
        )
        provider_nyse = create_mock_provider(
            supported_data={ProviderCapability.PRICE_HISTORY},
            supported_markets={"NYSE"},
        )

        ProviderRegistry.register("bist", provider_bist)
        ProviderRegistry.register("nyse", provider_nyse)

        result = ProviderRegistry.get_provider_for_capability(
            ProviderCapability.PRICE_HISTORY, market="BIST"
        )

        assert result == provider_bist

    def test_get_provider_for_capability_raises_if_none_supports(self):
        """Should raise ValueError if no provider supports capability."""
        _prevent_auto_initialize()
        provider = create_mock_provider(
            supported_data={ProviderCapability.PRICE_HISTORY}
        )
        ProviderRegistry.register("test", provider)

        with pytest.raises(ValueError) as exc_info:
            ProviderRegistry.get_provider_for_capability(
                ProviderCapability.KAP_FILINGS
            )

        assert "No provider supports" in str(exc_info.value)

    def test_get_provider_for_capability_returns_first_match(self):
        """Should return first provider that matches capability."""
        _prevent_auto_initialize()
        provider1 = create_mock_provider(
            supported_data={ProviderCapability.PRICE_HISTORY}
        )
        provider2 = create_mock_provider(
            supported_data={ProviderCapability.PRICE_HISTORY}
        )

        ProviderRegistry.register("first", provider1)
        ProviderRegistry.register("second", provider2)

        result = ProviderRegistry.get_provider_for_capability(
            ProviderCapability.PRICE_HISTORY
        )

        # Should return first registered
        assert result == provider1


class TestGetCapabilities:
    """Tests for getting provider capabilities."""

    def test_get_capabilities_returns_provider_caps(self):
        """Should return capabilities of registered provider."""
        caps = ProviderCapabilities(
            supported_data={ProviderCapability.PRICE_HISTORY, ProviderCapability.METRICS},
            supports_intraday=True,
        )
        provider = create_mock_provider()
        provider.capabilities = caps
        ProviderRegistry.register("test", provider)

        result = ProviderRegistry.get_capabilities("test")

        assert ProviderCapability.PRICE_HISTORY in result.supported_data
        assert ProviderCapability.METRICS in result.supported_data
        assert result.supports_intraday is True


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_get_default_provider_returns_borsapy(self):
        """Should return borsapy provider by default."""
        _prevent_auto_initialize()
        borsapy = create_mock_provider(
            supported_data={ProviderCapability.PRICE_HISTORY}
        )
        ProviderRegistry.register("borsapy", borsapy)

        result = get_default_provider()

        assert result == borsapy

    def test_get_default_provider_caches_result(self):
        """Should cache the default provider."""
        _prevent_auto_initialize()
        borsapy = create_mock_provider()
        ProviderRegistry.register("borsapy", borsapy)

        # Call twice - should return same instance
        result1 = get_default_provider()
        result2 = get_default_provider()

        assert result1 is result2

    def test_get_provider_for_prices(self):
        """Should return provider with PRICE_HISTORY capability."""
        _prevent_auto_initialize()
        provider = create_mock_provider(
            supported_data={ProviderCapability.PRICE_HISTORY}
        )
        ProviderRegistry.register("test", provider)

        result = get_provider_for_prices()

        assert result == provider

    def test_get_provider_for_financials(self):
        """Should return provider with FINANCIALS capability."""
        _prevent_auto_initialize()
        provider = create_mock_provider(
            supported_data={ProviderCapability.FINANCIALS}
        )
        ProviderRegistry.register("test", provider)

        result = get_provider_for_financials()

        assert result == provider

    def test_get_provider_for_metrics(self):
        """Should return provider with METRICS capability."""
        _prevent_auto_initialize()
        provider = create_mock_provider(
            supported_data={ProviderCapability.METRICS}
        )
        ProviderRegistry.register("test", provider)

        result = get_provider_for_metrics()

        assert result == provider


class TestKapFilingsProviderSelection:
    """Tests for KAP filings provider selection with fallback."""

    def test_get_provider_for_kap_filings_prefers_fallback(self):
        """Should prefer fallback_kap provider if available."""
        _prevent_auto_initialize()
        pykap = create_mock_provider(
            supported_data={ProviderCapability.KAP_FILINGS}
        )
        fallback_kap = create_mock_provider(
            supported_data={ProviderCapability.KAP_FILINGS}
        )

        ProviderRegistry.register("pykap", pykap)
        ProviderRegistry.register("fallback_kap", fallback_kap)

        result = get_provider_for_kap_filings()

        assert result == fallback_kap

    def test_get_provider_for_kap_filings_falls_back_to_capability(self):
        """Should fall back to capability selection if no fallback_kap."""
        _prevent_auto_initialize()
        pykap = create_mock_provider(
            supported_data={ProviderCapability.KAP_FILINGS}
        )

        ProviderRegistry.register("pykap", pykap)

        result = get_provider_for_kap_filings()

        assert result == pykap

    def test_get_provider_for_kap_filings_raises_if_none_available(self):
        """Should raise if no KAP filings provider available."""
        _prevent_auto_initialize()
        provider = create_mock_provider(
            supported_data={ProviderCapability.PRICE_HISTORY}
        )
        ProviderRegistry.register("test", provider)

        with pytest.raises(ValueError) as exc_info:
            get_provider_for_kap_filings()

        assert "No provider supports" in str(exc_info.value)


class TestInitialization:
    """Tests for registry initialization."""

    def test_initialize_only_once(self):
        """Should only initialize once even if called multiple times."""
        with patch.object(ProviderRegistry, "register") as mock_register:
            # Manually set initialized to test double initialization
            ProviderRegistry._initialized = True

            ProviderRegistry.initialize()

            # Should not call register since already initialized
            mock_register.assert_not_called()

    def test_initialize_registers_borsapy_if_available(self):
        """Should register borsapy provider if import succeeds."""
        mock_provider = MagicMock()

        with patch.dict(
            "sys.modules",
            {"app.services.data.providers.borsapy_provider": MagicMock(BorsapyProvider=lambda: mock_provider)},
        ):
            with patch("app.services.data.provider_registry.logger"):
                # Reset to force re-initialization
                ProviderRegistry._initialized = False
                ProviderRegistry._providers = {}

                ProviderRegistry.initialize()

                assert "borsapy" in ProviderRegistry._providers

    def test_initialize_handles_import_error(self):
        """Should handle ImportError gracefully during initialization."""
        ProviderRegistry._initialized = False
        ProviderRegistry._providers = {}

        # This should not raise - ImportError is caught and logged
        with patch("app.services.data.provider_registry.logger"):
            # Force re-initialization without providers
            ProviderRegistry.initialize()

        # Should be initialized even with no providers
        assert ProviderRegistry._initialized is True


class TestProviderCapabilitiesIntegration:
    """Integration tests for provider capability scenarios."""

    def test_multiple_capabilities_single_provider(self):
        """Should find provider with multiple capabilities."""
        _prevent_auto_initialize()
        provider = create_mock_provider(
            supported_data={
                ProviderCapability.PRICE_HISTORY,
                ProviderCapability.METRICS,
                ProviderCapability.FINANCIALS,
            }
        )
        ProviderRegistry.register("full", provider)

        # Should find same provider for different capabilities
        price_provider = ProviderRegistry.get_provider_for_capability(
            ProviderCapability.PRICE_HISTORY
        )
        metrics_provider = ProviderRegistry.get_provider_for_capability(
            ProviderCapability.METRICS
        )
        financials_provider = ProviderRegistry.get_provider_for_capability(
            ProviderCapability.FINANCIALS
        )

        assert price_provider == provider
        assert metrics_provider == provider
        assert financials_provider == provider

    def test_specialized_providers_for_capabilities(self):
        """Should select specialized providers for capabilities."""
        _prevent_auto_initialize()
        price_provider = create_mock_provider(
            supported_data={ProviderCapability.PRICE_HISTORY}
        )
        kap_provider = create_mock_provider(
            supported_data={ProviderCapability.KAP_FILINGS}
        )

        ProviderRegistry.register("prices", price_provider)
        ProviderRegistry.register("kap", kap_provider)

        result_prices = ProviderRegistry.get_provider_for_capability(
            ProviderCapability.PRICE_HISTORY
        )
        result_kap = ProviderRegistry.get_provider_for_capability(
            ProviderCapability.KAP_FILINGS
        )

        assert result_prices == price_provider
        assert result_kap == kap_provider