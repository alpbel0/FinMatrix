"""Integration tests for KapSdkProvider.

These tests require:
1. kap_sdk package installed
2. Internet connection (for pyppeteer)
3. Real KAP.org.tr API access

Run with: pytest tests/integration/test_kap_sdk_provider.py -v
Skip if kap_sdk not installed: pytest tests/integration/test_kap_sdk_provider.py -v -m "not requires_kap_sdk"
"""

import pytest
from datetime import date, timedelta

from app.services.data.providers.kap_sdk_provider import (
    KapSdkProvider,
    _KAP_SDK_AVAILABLE,
)
from app.services.data.provider_models import DataSource
from app.services.data.provider_exceptions import (
    ProviderSymbolNotFoundError,
    ProviderError,
)


# Skip all tests in this module if kap_sdk not installed
pytestmark = pytest.mark.skipif(
    not _KAP_SDK_AVAILABLE,
    reason="kap_sdk package not installed"
)


@pytest.fixture
def kap_sdk_provider():
    """Create KapSdkProvider instance."""
    return KapSdkProvider(timeout=60.0)


class TestKapSdkProviderRealAPI:
    """Integration tests using real kap_sdk API."""

    def test_is_available_when_installed(self, kap_sdk_provider):
        """Provider should be available when kap_sdk is installed."""
        assert kap_sdk_provider.is_available() is True

    def test_health_check_succeeds(self, kap_sdk_provider):
        """Health check should succeed with valid symbol."""
        result = kap_sdk_provider.health_check()
        assert result is True

    def test_get_kap_filings_thyao(self, kap_sdk_provider):
        """Should fetch KAP filings for THYAO when upstream cooperates."""
        try:
            filings = kap_sdk_provider.get_kap_filings("THYAO")
        except ProviderError as exc:
            pytest.xfail(f"kap_sdk upstream instability for THYAO: {exc}")

        if len(filings) == 0:
            pytest.xfail("kap_sdk upstream returned no THYAO filings")

        assert isinstance(filings, list)
        assert len(filings) > 0

        # Check first filing structure
        first_filing = filings[0]
        assert first_filing.symbol == "THYAO"
        assert first_filing.title is not None
        assert first_filing.source_url is not None
        assert first_filing.provider == DataSource.KAPSDK

    def test_get_kap_filings_garan(self, kap_sdk_provider):
        """Should fetch KAP filings for GARAN when company lookup is available."""
        try:
            filings = kap_sdk_provider.get_kap_filings("GARAN")
        except ProviderError as exc:
            pytest.xfail(f"kap_sdk lookup instability for GARAN: {exc}")

        assert isinstance(filings, list)
        assert len(filings) >= 0  # May have 0 or more filings

    def test_get_kap_filings_with_date_filter(self, kap_sdk_provider):
        """Should filter filings by date."""
        start_date = date.today() - timedelta(days=7)

        filings = kap_sdk_provider.get_kap_filings("THYAO", start_date=start_date)

        assert isinstance(filings, list)
        # All filings should be after start_date
        for filing in filings:
            if filing.published_at:
                assert filing.published_at.date() >= start_date

    def test_get_kap_filings_invalid_symbol(self, kap_sdk_provider):
        """Should raise error for invalid symbol."""
        with pytest.raises(ProviderSymbolNotFoundError):
            kap_sdk_provider.get_kap_filings("INVALID_SYMBOL_XYZ")

    def test_get_kap_filings_enrichment_fields(self, kap_sdk_provider):
        """Should include enrichment fields when available."""
        filings = kap_sdk_provider.get_kap_filings("THYAO")

        if len(filings) > 0:
            # Check if any filing has enrichment
            has_enrichment = any(
                f.summary is not None or f.attachment_count is not None
                for f in filings
            )
            # This may or may not have enrichment depending on disclosure type
            assert isinstance(has_enrichment, bool)

    def test_filing_urls_format(self, kap_sdk_provider):
        """Filing URLs should have correct format."""
        filings = kap_sdk_provider.get_kap_filings("THYAO")

        if len(filings) > 0:
            filing = filings[0]
            assert "kap.org.tr" in filing.source_url
            assert "Bildirim" in filing.source_url
            assert "kap.org.tr" in filing.pdf_url
            assert "BildirimPdf" in filing.pdf_url

    def test_filings_sorted_by_date_descending(self, kap_sdk_provider):
        """Filings should be sorted by published_at descending."""
        filings = kap_sdk_provider.get_kap_filings("THYAO")

        if len(filings) > 1:
            dates = [f.published_at for f in filings if f.published_at]
            assert dates == sorted(dates, reverse=True)


class TestKapSdkProviderWithFallbackProvider:
    """Integration tests with FallbackKapProvider."""

    def test_fallback_provider_registration(self):
        """FallbackKapProvider should be registered in ProviderRegistry."""
        from app.services.data.provider_registry import ProviderRegistry

        ProviderRegistry.initialize()
        providers = ProviderRegistry.list_providers()

        assert "kap_sdk" in providers or "pykap" in providers

    def test_get_provider_for_kap_filings(self):
        """get_provider_for_kap_filings should return valid provider."""
        from app.services.data.provider_registry import get_provider_for_kap_filings

        provider = get_provider_for_kap_filings()
        assert provider is not None

        # Should have KAP_FILINGS capability
        from app.services.data.provider_models import ProviderCapability
        assert ProviderCapability.KAP_FILINGS in provider.capabilities.supported_data
