"""Unit tests for KapSdkProvider."""

import pytest
from datetime import date, datetime
from unittest.mock import MagicMock, patch, AsyncMock

from app.services.data.providers.kap_sdk_provider import (
    KapSdkProvider,
    map_kap_sdk_exception,
    _KAP_SDK_AVAILABLE,
)
from app.services.data.provider_models import KapFiling, DataSource
from app.services.data.provider_exceptions import (
    ProviderConnectionError,
    ProviderTimeoutError,
    ProviderRateLimitError,
    ProviderSymbolNotFoundError,
    ProviderError,
    ProviderAPIError,
)


class TestMapKapSdkException:
    """Tests for exception mapping."""

    def test_connection_error_mapped(self):
        """Connection errors should map to ProviderConnectionError."""
        exc = ConnectionError("Failed to connect")
        result = map_kap_sdk_exception(exc)
        assert isinstance(result, ProviderConnectionError)
        assert result.provider == "kap_sdk"

    def test_timeout_error_mapped(self):
        """Timeout errors should map to ProviderTimeoutError."""
        exc = TimeoutError("Request timed out")
        result = map_kap_sdk_exception(exc)
        assert isinstance(result, ProviderTimeoutError)
        assert result.timeout_seconds == 30.0

    def test_async_timeout_error_mapped(self):
        """Async timeout errors should also map to ProviderTimeoutError."""
        import asyncio
        exc = asyncio.TimeoutError()
        result = map_kap_sdk_exception(exc)
        assert isinstance(result, ProviderTimeoutError)

    def test_404_mapped_to_data_not_found(self):
        """404 status should indicate data not found."""
        exc = Exception("Not found")
        exc.status_code = 404
        result = map_kap_sdk_exception(exc)
        # Check for "not found" in the mapped error
        assert "not found" in str(result).lower()

    def test_429_mapped_to_rate_limit(self):
        """429 status should map to rate limit error."""
        exc = Exception("Rate limit exceeded")
        exc.status_code = 429
        result = map_kap_sdk_exception(exc)
        assert isinstance(result, ProviderRateLimitError)

    def test_generic_exception_wrapped(self):
        """Generic exceptions should be wrapped in ProviderError."""
        exc = ValueError("Some error")
        result = map_kap_sdk_exception(exc)
        assert isinstance(result, ProviderError)
        assert result.provider == "kap_sdk"


class TestKapSdkProviderAvailability:
    """Tests for provider availability checks."""

    def test_is_available_returns_flag(self):
        """is_available should return the _KAP_SDK_AVAILABLE flag."""
        provider = KapSdkProvider()
        assert provider.is_available() == _KAP_SDK_AVAILABLE

    def test_capabilities_include_kap_filings(self):
        """Provider should declare KAP_FILINGS capability."""
        provider = KapSdkProvider()
        caps = provider.capabilities
        from app.services.data.provider_models import ProviderCapability
        assert ProviderCapability.KAP_FILINGS in caps.supported_data


class TestKapSdkProviderMapping:
    """Tests for disclosure to filing mapping."""

    def test_parse_kap_publish_date_standard_format(self):
        """Should parse standard KAP date format."""
        provider = KapSdkProvider()

        result = provider._parse_kap_publish_date("08.04.2026 14:30:00")
        assert result == datetime(2026, 4, 8, 14, 30, 0)

    def test_parse_kap_publish_date_alternative_format(self):
        """Should parse alternative date formats."""
        provider = KapSdkProvider()

        # ISO format
        result = provider._parse_kap_publish_date("2026-04-08T14:30:00")
        assert result == datetime(2026, 4, 8, 14, 30, 0)

        # Date only
        result2 = provider._parse_kap_publish_date("2026-04-08")
        assert result2 == datetime(2026, 4, 8, 0, 0, 0)

    def test_parse_kap_publish_date_none_on_invalid(self):
        """Should return None for invalid date strings."""
        provider = KapSdkProvider()

        result = provider._parse_kap_publish_date("invalid-date")
        assert result is None

        result2 = provider._parse_kap_publish_date(None)
        assert result2 is None


class TestKapSdkProviderAnnouncementMapping:
    """Tests for announcement to KapFiling mapping."""

    def test_map_announcement_to_filing(self):
        """Should correctly map announcement to KapFiling."""
        provider = KapSdkProvider()

        # Create mock announcement
        mock_basic = MagicMock()
        mock_basic.disclosureIndex = 12345678
        mock_basic.title = "Test Financial Report"
        mock_basic.disclosureClass = "FR"
        mock_basic.publishDate = "08.04.2026 14:30:00"
        mock_basic.attachmentCount = 2
        mock_basic.isLate = False
        mock_basic.relatedStocks = None

        mock_detail = MagicMock()
        mock_detail.summary = "Test summary text"

        mock_announcement = MagicMock()
        mock_announcement.disclosureBasic = mock_basic
        mock_announcement.disclosureDetail = mock_detail

        result = provider._map_announcement_to_filing(mock_announcement, "THYAO")

        assert result is not None
        assert result.symbol == "THYAO"
        assert result.title == "Test Financial Report"
        assert result.filing_type == "FR"
        assert result.provider == DataSource.KAPSDK
        assert result.source_url == "https://www.kap.org.tr/tr/Bildirim/12345678"
        assert result.pdf_url == "https://www.kap.org.tr/tr/api/BildirimPdf/12345678"
        assert result.summary == "Test summary text"
        assert result.attachment_count == 2

    def test_map_announcement_returns_none_on_error(self):
        """Should return None when mapping fails."""
        provider = KapSdkProvider()

        # Invalid announcement
        mock_announcement = MagicMock()
        mock_announcement.disclosureBasic = None

        result = provider._map_announcement_to_filing(mock_announcement, "THYAO")
        assert result is None


class TestKapSdkProviderUnsupportedMethods:
    """Tests for methods not supported by KapSdkProvider."""

    def test_get_price_history_returns_empty(self):
        """Price history should return empty list."""
        provider = KapSdkProvider()
        result = provider.get_price_history("THYAO")
        assert result == []

    def test_get_stock_snapshot_raises_error(self):
        """Stock snapshot should raise ProviderDataNotFoundError."""
        from app.services.data.provider_exceptions import ProviderDataNotFoundError

        provider = KapSdkProvider()
        with pytest.raises(ProviderDataNotFoundError):
            provider.get_stock_snapshot("THYAO")

    def test_get_financial_statements_returns_empty(self):
        """Financial statements should return empty list."""
        provider = KapSdkProvider()
        from app.services.data.provider_models import PeriodType
        result = provider.get_financial_statements("THYAO", PeriodType.ANNUAL)
        assert result == []

    def test_get_company_profile_raises_error(self):
        """Company profile should raise ProviderDataNotFoundError."""
        from app.services.data.provider_exceptions import ProviderDataNotFoundError

        provider = KapSdkProvider()
        with pytest.raises(ProviderDataNotFoundError):
            provider.get_company_profile("THYAO")

    def test_batch_price_update_returns_empty(self):
        """Batch price update should return empty dict."""
        provider = KapSdkProvider()
        result = provider.batch_price_update(["THYAO", "GARAN"])
        assert result == {}