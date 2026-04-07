"""Unit tests for FallbackKapProvider."""

import pytest
from datetime import date, datetime
from unittest.mock import MagicMock, patch

from app.services.data.providers.fallback_kap_provider import FallbackKapProvider
from app.services.data.provider_models import KapFiling, DataSource, ProviderCapabilities
from app.services.data.provider_exceptions import (
    ProviderConnectionError,
    ProviderTimeoutError,
    ProviderRateLimitError,
    ProviderSymbolNotFoundError,
    ProviderDataNotFoundError,
    ProviderAPIError,
    ProviderError,
)


def create_mock_filing(
    disclosure_index: int,
    symbol: str = "THYAO",
    title: str = "Test Filing",
    filing_type: str = "FR",
    provider: DataSource = DataSource.PYKAP,
    summary: str | None = None,
    attachment_count: int | None = None,
) -> KapFiling:
    """Factory to create KapFiling for testing."""
    return KapFiling(
        symbol=symbol,
        title=title,
        filing_type=filing_type,
        source_url=f"https://www.kap.org.tr/tr/Bildirim/{disclosure_index}",
        pdf_url=f"https://www.kap.org.tr/tr/api/BildirimPdf/{disclosure_index}",
        published_at=datetime(2026, 4, 8, 14, 30, 0),
        provider=provider,
        summary=summary,
        attachment_count=attachment_count,
    )


class TestFallbackKapProviderInit:
    """Tests for FallbackKapProvider initialization."""

    def test_init_with_primary_and_fallback(self):
        """Should initialize with both providers."""
        primary = MagicMock()
        fallback = MagicMock()
        fallback.is_available.return_value = True

        provider = FallbackKapProvider(primary=primary, fallback=fallback)

        assert provider._primary == primary
        assert provider._fallback == fallback
        assert provider._fallback_enabled is True

    def test_init_fallback_disabled_when_none(self):
        """Should disable fallback when None provided."""
        primary = MagicMock()

        provider = FallbackKapProvider(primary=primary, fallback=None)

        assert provider._fallback is None
        assert provider._fallback_enabled is False

    def test_capabilities_from_primary(self):
        """Should inherit capabilities from primary."""
        primary = MagicMock()
        primary.capabilities = ProviderCapabilities(
            supported_data={"kap_filings"},
            timeout_seconds=30.0,
            retry_count=3,
        )

        provider = FallbackKapProvider(primary=primary)
        caps = provider.capabilities

        assert caps.timeout_seconds == 30.0
        assert caps.retry_count == 3


class TestFallbackKapProviderRetriableError:
    """Tests for retriable error detection."""

    def test_connection_error_is_retriable(self):
        """Connection errors should trigger fallback."""
        primary = MagicMock()
        provider = FallbackKapProvider(primary=primary)

        error = ProviderConnectionError("Connection failed", provider="pykap")
        assert provider._is_retriable_error(error) is True

    def test_timeout_error_is_retriable(self):
        """Timeout errors should trigger fallback."""
        primary = MagicMock()
        provider = FallbackKapProvider(primary=primary)

        error = ProviderTimeoutError(timeout_seconds=30.0, provider="pykap")
        assert provider._is_retriable_error(error) is True

    def test_rate_limit_error_is_retriable(self):
        """Rate limit errors should trigger fallback."""
        primary = MagicMock()
        provider = FallbackKapProvider(primary=primary)

        error = ProviderRateLimitError(provider="pykap")
        assert provider._is_retriable_error(error) is True

    def test_api_error_5xx_is_retriable(self):
        """5xx API errors should trigger fallback."""
        primary = MagicMock()
        provider = FallbackKapProvider(primary=primary)

        error = ProviderAPIError("Server error", status_code=500, provider="pykap")
        assert provider._is_retriable_error(error) is True

    def test_api_error_4xx_is_not_retriable(self):
        """4xx API errors should NOT trigger fallback."""
        primary = MagicMock()
        provider = FallbackKapProvider(primary=primary)

        error = ProviderAPIError("Bad request", status_code=400, provider="pykap")
        assert provider._is_retriable_error(error) is False

    def test_symbol_not_found_is_not_retriable(self):
        """SymbolNotFoundError should NOT trigger fallback."""
        primary = MagicMock()
        provider = FallbackKapProvider(primary=primary)

        error = ProviderSymbolNotFoundError(symbol="INVALID", provider="pykap")
        assert provider._is_retriable_error(error) is False

    def test_data_not_found_is_not_retriable(self):
        """DataNotFoundError should NOT trigger fallback."""
        primary = MagicMock()
        provider = FallbackKapProvider(primary=primary)

        error = ProviderDataNotFoundError(symbol="THYAO", data_type="filing", provider="pykap")
        assert provider._is_retriable_error(error) is False


class TestFallbackKapProviderDeduplication:
    """Tests for disclosure index extraction and deduplication."""

    def test_extract_disclosure_index_valid_url(self):
        """Should extract index from valid URL."""
        primary = MagicMock()
        provider = FallbackKapProvider(primary=primary)

        filing = create_mock_filing(12345678)
        result = provider._extract_disclosure_index(filing)

        assert result == 12345678

    def test_extract_disclosure_index_none_url(self):
        """Should return None when URL is None."""
        primary = MagicMock()
        provider = FallbackKapProvider(primary=primary)

        filing = KapFiling(symbol="THYAO", title="Test", source_url=None)
        result = provider._extract_disclosure_index(filing)

        assert result is None


class TestFallbackKapProviderEnrichment:
    """Tests for primary enrichment with fallback metadata."""

    def test_enrich_primary_with_fallback(self):
        """Should enrich primary filings with fallback metadata."""
        primary = MagicMock()
        provider = FallbackKapProvider(primary=primary)

        # Primary filing without enrichment
        primary_filing = create_mock_filing(
            disclosure_index=12345678,
            title="Financial Report",
            provider=DataSource.PYKAP,
            summary=None,
            attachment_count=None,
        )

        # Fallback filing with enrichment
        fallback_filing = create_mock_filing(
            disclosure_index=12345678,
            title="Financial Report",
            provider=DataSource.KAPSDK,
            summary="Detailed summary from kap_sdk",
            attachment_count=3,
        )

        enriched = provider._enrich_primary_with_fallback(
            [primary_filing], [fallback_filing]
        )

        assert len(enriched) == 1
        assert enriched[0].summary == "Detailed summary from kap_sdk"
        assert enriched[0].attachment_count == 3
        # Provider attribution should remain primary
        assert enriched[0].provider == DataSource.PYKAP

    def test_enrich_preserves_primary_when_no_match(self):
        """Should keep primary filing unchanged when no fallback match."""
        primary = MagicMock()
        provider = FallbackKapProvider(primary=primary)

        primary_filing = create_mock_filing(
            disclosure_index=11111111,
            title="Unique Primary Filing",
            provider=DataSource.PYKAP,
        )

        fallback_filing = create_mock_filing(
            disclosure_index=22222222,
            title="Different Fallback Filing",
            provider=DataSource.KAPSDK,
            summary="Fallback summary",
        )

        enriched = provider._enrich_primary_with_fallback(
            [primary_filing], [fallback_filing]
        )

        assert len(enriched) == 1
        assert enriched[0].source_url.endswith("/11111111")
        assert enriched[0].summary is None  # No enrichment


class TestFallbackKapProviderFlow:
    """Tests for fallback flow logic."""

    def test_primary_success_returns_primary_results(self):
        """When primary succeeds, should return primary results."""
        primary = MagicMock()
        primary.get_kap_filings.return_value = [
            create_mock_filing(11111111, provider=DataSource.PYKAP),
            create_mock_filing(11111112, provider=DataSource.PYKAP),
        ]

        fallback = MagicMock()
        fallback.get_kap_filings.return_value = [
            create_mock_filing(11111111, provider=DataSource.KAPSDK, summary="Enriched"),
        ]

        provider = FallbackKapProvider(primary=primary, fallback=fallback)
        results = provider.get_kap_filings("THYAO")

        # Primary should be called
        primary.get_kap_filings.assert_called_once()
        # Should have 2 results (primary filings, enriched)
        assert len(results) == 2
        assert provider._last_provider_used == "pykap"

    def test_primary_failure_triggers_fallback(self):
        """When primary fails with retriable error, should try fallback."""
        primary = MagicMock()
        primary.get_kap_filings.side_effect = ProviderConnectionError(
            "Connection failed", provider="pykap"
        )

        fallback = MagicMock()
        fallback.get_kap_filings.return_value = [
            create_mock_filing(22222222, provider=DataSource.KAPSDK),
        ]

        provider = FallbackKapProvider(primary=primary, fallback=fallback)
        results = provider.get_kap_filings("THYAO")

        # Both should be called
        primary.get_kap_filings.assert_called_once()
        fallback.get_kap_filings.assert_called_once()
        # Should have fallback results
        assert len(results) == 1
        assert provider._last_provider_used == "kap_sdk"

    def test_primary_non_retriable_failure_raises(self):
        """Non-retriable primary failure should raise without fallback."""
        primary = MagicMock()
        primary.get_kap_filings.side_effect = ProviderSymbolNotFoundError(
            symbol="INVALID", provider="pykap"
        )

        fallback = MagicMock()

        provider = FallbackKapProvider(primary=primary, fallback=fallback)

        with pytest.raises(ProviderSymbolNotFoundError):
            provider.get_kap_filings("INVALID")

        # Fallback should NOT be called
        fallback.get_kap_filings.assert_not_called()

    def test_both_failures_raises_primary_error(self):
        """When both providers fail, should raise primary error."""
        primary = MagicMock()
        primary.get_kap_filings.side_effect = ProviderTimeoutError(
            timeout_seconds=30.0, provider="pykap"
        )

        fallback = MagicMock()
        fallback.get_kap_filings.side_effect = ProviderError(
            "Fallback also failed", provider="kap_sdk"
        )

        provider = FallbackKapProvider(primary=primary, fallback=fallback)

        with pytest.raises(ProviderTimeoutError):
            provider.get_kap_filings("THYAO")


class TestFallbackKapProviderDelegation:
    """Tests for method delegation to primary."""

    def test_get_company_profile_delegates_to_primary(self):
        """Company profile should delegate to primary only."""
        primary = MagicMock()
        primary.get_company_profile.return_value = MagicMock()

        fallback = MagicMock()

        provider = FallbackKapProvider(primary=primary, fallback=fallback)
        provider.get_company_profile("THYAO")

        primary.get_company_profile.assert_called_once_with("THYAO")
        fallback.get_company_profile.assert_not_called()

    def test_health_check_primary_only(self):
        """Health check should only require primary to be healthy."""
        primary = MagicMock()
        primary.health_check.return_value = True

        fallback = MagicMock()
        fallback.health_check.return_value = False

        provider = FallbackKapProvider(primary=primary, fallback=fallback)
        result = provider.health_check()

        assert result is True  # Primary healthy, fallback unhealthy