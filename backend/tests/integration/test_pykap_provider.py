"""Integration tests for PykapProvider with real API calls.

Tests use real pykap API calls to verify provider functionality.
Test symbols: THYAO, GARAN, ASELS (as specified in roadmap).
"""

import requests
import pytest
from datetime import date, timedelta

from app.services.data.providers.pykap_provider import PykapProvider
from app.services.data.provider_models import DataSource, ProviderCapability
from app.services.data.provider_exceptions import (
    ProviderDataNotFoundError,
    ProviderSymbolNotFoundError,
    ProviderError,
)


# Test symbols per roadmap specification
TEST_SYMBOLS = ["THYAO", "GARAN", "ASELS"]


@pytest.fixture(scope="module")
def provider():
    """Create PykapProvider instance for tests."""
    return PykapProvider(timeout=30.0, retry_count=2)


class TestPykapProviderHealth:
    """Health check and basic functionality tests."""

    def test_health_check(self, provider):
        """Verify provider is operational."""
        result = provider.health_check()
        assert result is True, "Provider health check should pass"

    def test_capabilities(self, provider):
        """Verify provider capabilities are correct."""
        caps = provider.capabilities

        assert "BIST" in caps.supported_markets
        assert caps.supports_intraday is False  # pykap doesn't support intraday
        assert caps.supports_quarterly_financials is False  # pykap financials are parsed differently
        assert caps.max_history_days >= 3650

        # Check required capabilities
        assert ProviderCapability.KAP_FILINGS in caps.supported_data
        assert ProviderCapability.COMPANY_PROFILE in caps.supported_data

        # pykap should NOT have price/financial capabilities
        assert ProviderCapability.PRICE_HISTORY not in caps.supported_data
        assert ProviderCapability.METRICS not in caps.supported_data
        assert ProviderCapability.FINANCIALS not in caps.supported_data


class TestPykapProviderKapFilings:
    """KAP filings tests with real API."""

    @pytest.mark.parametrize("symbol", TEST_SYMBOLS)
    def test_get_kap_filings_default(self, provider, symbol):
        """Fetch KAP filings with default settings (last 30 days)."""
        filings = provider.get_kap_filings(symbol)

        assert isinstance(filings, list), f"Should return a list for {symbol}"
        # Filings may or may not be available within 30 days
        if len(filings) > 0:
            assert all(f.symbol == symbol.upper() for f in filings)
            assert all(f.provider == DataSource.PYKAP for f in filings)
            assert all(f.source_url is not None for f in filings), "All filings should have source_url"

    @pytest.mark.parametrize("symbol", TEST_SYMBOLS)
    def test_kap_filings_structure(self, provider, symbol):
        """Verify KapFiling structure."""
        filings = provider.get_kap_filings(symbol)

        if len(filings) > 0:
            filing = filings[0]

            # Required fields
            assert filing.symbol == symbol.upper()
            assert filing.title is not None
            assert len(filing.title) > 0

            # Provider attribution
            assert filing.provider == DataSource.PYKAP

            # Source URL should be valid
            assert filing.source_url is not None
            assert "kap.org.tr" in filing.source_url.lower()
            assert filing.pdf_url is not None
            assert "/tr/api/BildirimPdf/" in filing.pdf_url

    def test_kap_filing_pdf_url_is_downloadable(self, provider):
        """Verify generated PDF URL resolves to a real PDF."""
        filings = provider.get_kap_filings(
            "THYAO",
            start_date=date.today() - timedelta(days=365),
            filing_types=["FAR"],
        )
        assert len(filings) > 0

        response = requests.get(filings[0].pdf_url, timeout=30)

        assert response.status_code == 200
        assert response.headers["Content-Type"] == "application/pdf"

    def test_kap_filings_with_start_date(self, provider):
        """Test filing retrieval with specific date range."""
        start_date = date.today() - timedelta(days=90)

        filings = provider.get_kap_filings("THYAO", start_date=start_date)

        assert isinstance(filings, list)
        # With 90 days, should have more chance of finding filings
        # but we still accept empty results as KAP API might have issues

    def test_kap_filings_with_filing_types(self, provider):
        """Test filing retrieval with specific types."""
        # Fetch FAR (activity reports) specifically
        filings = provider.get_kap_filings("THYAO", filing_types=["FAR"])

        assert isinstance(filings, list)
        if len(filings) > 0:
            # All filings should be FAR type
            for filing in filings:
                assert filing.filing_type == "FAR"

    def test_kap_filings_invalid_symbol(self, provider):
        """Test error handling for invalid symbol."""
        with pytest.raises((ProviderSymbolNotFoundError, ProviderError)):
            provider.get_kap_filings("INVALID_SYMBOL_XYZ")


class TestPykapProviderCompanyProfile:
    """Company profile tests with real API."""

    @pytest.mark.parametrize("symbol", TEST_SYMBOLS)
    def test_get_company_profile(self, provider, symbol):
        """Fetch company metadata from KAP."""
        profile = provider.get_company_profile(symbol)

        assert profile.symbol == symbol.upper()
        assert profile.exchange == "BIST"
        assert profile.source == DataSource.PYKAP

        # Company name should exist
        assert profile.company_name is not None, f"Should have company_name for {symbol}"
        assert len(profile.company_name) > 0

    def test_company_profile_invalid_symbol(self, provider):
        """Test error handling for invalid symbol."""
        with pytest.raises(ProviderSymbolNotFoundError):
            provider.get_company_profile("INVALID_SYMBOL_XYZ")


class TestPykapProviderUnsupported:
    """Test methods that are not supported by pykap."""

    def test_get_price_history_returns_empty(self, provider):
        """Price history should return empty list (not supported)."""
        bars = provider.get_price_history("THYAO")
        assert bars == [], "Pykap should return empty list for price history"

    def test_get_stock_snapshot_raises_error(self, provider):
        """Stock snapshot should raise ProviderDataNotFoundError."""
        with pytest.raises(ProviderDataNotFoundError):
            provider.get_stock_snapshot("THYAO")

    def test_get_financial_statements_returns_empty(self, provider):
        """Financial statements should return empty list (not supported)."""
        from app.services.data.provider_models import PeriodType
        statements = provider.get_financial_statements(
            "THYAO",
            period_type=PeriodType.ANNUAL,
            last_n=3
        )
        assert statements == [], "Pykap should return empty list for financial statements"

    def test_batch_price_update_returns_empty(self, provider):
        """Batch price update should return empty dict (not supported)."""
        result = provider.batch_price_update(["THYAO", "GARAN"])
        assert result == {}, "Pykap should return empty dict for batch price update"


class TestPykapProviderRegistryIntegration:
    """Test provider registry integration."""

    def test_registry_has_pykap(self):
        """Verify registry can return pykap provider."""
        from app.services.data.provider_registry import ProviderRegistry

        ProviderRegistry.initialize()
        provider = ProviderRegistry.get_provider("pykap")

        assert isinstance(provider, PykapProvider)
        assert provider.health_check() is True

    def test_get_provider_for_kap_filings(self):
        """Verify capability-based selection for KAP filings."""
        from app.services.data.provider_registry import get_provider_for_kap_filings

        provider = get_provider_for_kap_filings()

        # Should return a provider that supports KAP_FILINGS
        assert ProviderCapability.KAP_FILINGS in provider.capabilities.supported_data

    def test_list_providers_includes_pykap(self):
        """Verify pykap is in the list of registered providers."""
        from app.services.data.provider_registry import ProviderRegistry

        ProviderRegistry.initialize()
        providers = ProviderRegistry.list_providers()

        assert "pykap" in providers
        assert "borsapy" in providers  # Both should be registered


class TestPykapProviderExceptionMapping:
    """Test exception mapping."""

    def test_invalid_ticker_raises_symbol_not_found(self, provider):
        """Verify invalid ticker raises ProviderSymbolNotFoundError."""
        with pytest.raises(ProviderSymbolNotFoundError) as exc_info:
            provider._create_company("INVALID_TICKER_XYZ")

        assert exc_info.value.symbol == "INVALID_TICKER_XYZ"
        assert exc_info.value.provider == "pykap"
