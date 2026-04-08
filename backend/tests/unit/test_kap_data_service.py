"""Unit tests for kap_data_service.

Tests the service layer with mocked providers and database operations.
"""

import pytest
from datetime import date, datetime
from unittest.mock import AsyncMock, patch, MagicMock
import uuid

from sqlalchemy import select

from app.models.stock import Stock
from app.models.pipeline_log import PipelineLog
from app.services.data.kap_data_service import (
    KapSyncResult,
    KapBatchSyncResult,
    sync_kap_filings,
    batch_sync_kap_filings,
    validate_filing_fields,
    DEFAULT_FILING_TYPES,
)
from app.services.data.mappers.kap_report_mapper import normalize_related_stocks
from app.services.data.provider_exceptions import (
    ProviderConnectionError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderSymbolNotFoundError,
    ProviderDataNotFoundError,
)
from app.services.data.provider_models import KapFiling, DataSource
from tests.factories import create_kap_filing, create_kap_filings_batch


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_provider():
    """Create a mock provider for testing."""
    provider = MagicMock()
    provider.get_kap_filings = MagicMock()
    return provider


@pytest.fixture
def sample_kap_filings():
    """Create sample KAP filings for testing."""
    return create_kap_filings_batch(symbol="THYAO", num_filings=5)


# ============================================================================
# normalize_related_stocks Tests
# ============================================================================


class TestNormalizeRelatedStocks:
    """Tests for normalize_related_stocks helper function."""

    def test_handles_none_input(self):
        """None input should return None."""
        result = normalize_related_stocks(None)
        assert result is None

    def test_handles_empty_string(self):
        """Empty string should return None."""
        result = normalize_related_stocks("")
        assert result is None

    def test_handles_whitespace_only(self):
        """Whitespace-only string should return None."""
        result = normalize_related_stocks("   ")
        assert result is None

    def test_normalizes_single_symbol(self):
        """Single symbol should be normalized to uppercase."""
        result = normalize_related_stocks("thyao")
        assert result == ["THYAO"]

    def test_normalizes_multiple_symbols(self):
        """Multiple symbols should be normalized and split."""
        result = normalize_related_stocks("thyao, garan, asels")
        assert result == ["THYAO", "GARAN", "ASELS"]

    def test_removes_duplicates_preserving_order(self):
        """Duplicate symbols should be removed, order preserved."""
        result = normalize_related_stocks("THYAO, GARAN, THYAO, ASELS, GARAN")
        assert result == ["THYAO", "GARAN", "ASELS"]

    def test_trims_whitespace(self):
        """Whitespace around symbols should be trimmed."""
        result = normalize_related_stocks("  THYAO  ,  GARAN  ")
        assert result == ["THYAO", "GARAN"]

    def test_filters_empty_entries(self):
        """Empty entries should be filtered out."""
        result = normalize_related_stocks("THYAO,,GARAN,")
        assert result == ["THYAO", "GARAN"]


# ============================================================================
# validate_filing_fields Tests
# ============================================================================


class TestValidateFilingFields:
    """Tests for validate_filing_fields function."""

    def test_valid_filing_no_warnings(self):
        """Valid filing should have no warnings."""
        filing = create_kap_filing(
            title="Financial Report",
        )
        warnings = validate_filing_fields(filing)
        assert warnings == []

    def test_missing_source_url_warning(self):
        """Missing source_url should generate warning."""
        filing = KapFiling(
            symbol="THYAO",
            title="Financial Report",
            filing_type="FR",
            source_url=None,
            pdf_url="https://kap.org.tr/Pdf/123",
            provider=DataSource.PYKAP,
        )
        warnings = validate_filing_fields(filing)
        assert len(warnings) == 1
        assert "source_url" in warnings[0]

    def test_missing_pdf_url_warning(self):
        """Missing pdf_url should generate warning."""
        filing = KapFiling(
            symbol="THYAO",
            title="Financial Report",
            filing_type="FR",
            source_url="https://kap.org.tr/Bildirim/123",
            pdf_url=None,
            provider=DataSource.PYKAP,
        )
        warnings = validate_filing_fields(filing)
        assert len(warnings) == 1
        assert "pdf_url" in warnings[0]

    def test_missing_both_urls_warnings(self):
        """Missing both URLs should generate two warnings."""
        filing = KapFiling(
            symbol="THYAO",
            title="Financial Report",
            filing_type="FR",
            source_url=None,
            pdf_url=None,
            provider=DataSource.PYKAP,
        )
        warnings = validate_filing_fields(filing)
        assert len(warnings) == 2


# ============================================================================
# sync_kap_filings Tests
# ============================================================================


class TestSyncKapFilings:
    """Tests for sync_kap_filings function."""

    @pytest.mark.asyncio
    async def test_sync_success_returns_result(self, db_session, mock_provider, sample_kap_filings):
        """Successful sync should return KapSyncResult with count."""
        # Setup: Create stock in database
        stock = Stock(symbol="THYAO", company_name="Test Stock", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        # Mock provider to return filings
        mock_provider.get_kap_filings.return_value = sample_kap_filings

        with patch(
            "app.services.data.kap_data_service.get_provider_for_kap_filings",
            return_value=mock_provider
        ):
            result = await sync_kap_filings(db_session, "THYAO", filing_types=["FR"], days_back=30)

        assert result.success is True
        assert result.symbol == "THYAO"
        assert result.filings_processed == 5
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_sync_with_multiple_types(self, db_session, mock_provider, sample_kap_filings):
        """Should pass filing_types to provider."""
        stock = Stock(symbol="THYAO", company_name="Test Stock", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        mock_provider.get_kap_filings.return_value = sample_kap_filings

        with patch(
            "app.services.data.kap_data_service.get_provider_for_kap_filings",
            return_value=mock_provider
        ):
            result = await sync_kap_filings(
                db_session, "THYAO", filing_types=["FR", "FAR"], days_back=30
            )

        assert result.success is True
        # Verify provider was called with correct filing_types
        call_args = mock_provider.get_kap_filings.call_args
        assert call_args.kwargs.get("filing_types") == ["FR", "FAR"]

    @pytest.mark.asyncio
    async def test_sync_handles_stock_not_found(self, db_session, mock_provider):
        """Should return failed result for unknown symbol."""
        # No stock in database

        with patch(
            "app.services.data.kap_data_service.get_provider_for_kap_filings",
            return_value=mock_provider
        ):
            result = await sync_kap_filings(db_session, "INVALID", filing_types=["FR"])

        assert result.success is False
        assert result.symbol == "INVALID"
        assert "not found" in result.error_message.lower()
        # Provider should not be called
        mock_provider.get_kap_filings.assert_not_called()

    @pytest.mark.asyncio
    async def test_sync_handles_empty_data(self, db_session, mock_provider):
        """Empty filings should succeed with 0 records."""
        # Setup stock
        stock = Stock(symbol="THYAO", company_name="Test Stock", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        # Mock provider to return empty list
        mock_provider.get_kap_filings.return_value = []

        with patch(
            "app.services.data.kap_data_service.get_provider_for_kap_filings",
            return_value=mock_provider
        ):
            result = await sync_kap_filings(db_session, "THYAO", filing_types=["FR"])

        assert result.success is True
        assert result.filings_processed == 0

    @pytest.mark.asyncio
    async def test_sync_handles_provider_symbol_not_found(self, db_session, mock_provider):
        """ProviderSymbolNotFoundError should return failed result."""
        stock = Stock(symbol="INVALID", company_name="Test", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        mock_provider.get_kap_filings.side_effect = ProviderSymbolNotFoundError("INVALID")

        with patch(
            "app.services.data.kap_data_service.get_provider_for_kap_filings",
            return_value=mock_provider
        ):
            result = await sync_kap_filings(db_session, "INVALID", filing_types=["FR"])

        assert result.success is False
        assert "not found" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_sync_handles_provider_data_not_found(self, db_session, mock_provider):
        """ProviderDataNotFoundError should succeed with 0 records."""
        stock = Stock(symbol="THYAO", company_name="Test", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        mock_provider.get_kap_filings.side_effect = ProviderDataNotFoundError("No data")

        with patch(
            "app.services.data.kap_data_service.get_provider_for_kap_filings",
            return_value=mock_provider
        ):
            result = await sync_kap_filings(db_session, "THYAO", filing_types=["FR"])

        assert result.success is True
        assert result.filings_processed == 0

    @pytest.mark.asyncio
    async def test_sync_retries_on_connection_error(self, db_session, mock_provider, sample_kap_filings):
        """Should retry on ProviderConnectionError."""
        stock = Stock(symbol="THYAO", company_name="Test", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        # Fail twice, succeed on third try
        mock_provider.get_kap_filings.side_effect = [
            ProviderConnectionError("Connection failed"),
            ProviderConnectionError("Connection failed"),
            sample_kap_filings,
        ]

        with patch(
            "app.services.data.kap_data_service.get_provider_for_kap_filings",
            return_value=mock_provider
        ):
            result = await sync_kap_filings(db_session, "THYAO", filing_types=["FR"], max_retries=3)

        assert result.success is True
        assert result.filings_processed == 5
        assert mock_provider.get_kap_filings.call_count == 3

    @pytest.mark.asyncio
    async def test_sync_fails_after_max_retries(self, db_session, mock_provider):
        """Should fail after max retries exceeded."""
        stock = Stock(symbol="THYAO", company_name="Test", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        # Always fail
        mock_provider.get_kap_filings.side_effect = ProviderConnectionError("Connection failed")

        with patch(
            "app.services.data.kap_data_service.get_provider_for_kap_filings",
            return_value=mock_provider
        ):
            result = await sync_kap_filings(db_session, "THYAO", filing_types=["FR"], max_retries=3)

        assert result.success is False
        assert "retries" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_sync_normalizes_symbol(self, db_session, mock_provider, sample_kap_filings):
        """Symbol should be normalized to uppercase."""
        stock = Stock(symbol="THYAO", company_name="Test", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        mock_provider.get_kap_filings.return_value = sample_kap_filings

        with patch(
            "app.services.data.kap_data_service.get_provider_for_kap_filings",
            return_value=mock_provider
        ):
            result = await sync_kap_filings(db_session, "thyao", filing_types=["FR"])

        assert result.symbol == "THYAO"

    @pytest.mark.asyncio
    async def test_sync_validation_warnings(self, db_session, mock_provider):
        """Missing source_url should generate validation warnings."""
        stock = Stock(symbol="THYAO", company_name="Test", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        # Create filing without source_url (use KapFiling directly to bypass factory)
        filing_no_source = KapFiling(
            symbol="THYAO",
            title="Test Filing Without Source",
            filing_type="FR",
            source_url=None,
            pdf_url="https://kap.org.tr/Pdf/123",
            provider=DataSource.PYKAP,
        )
        filing_with_source = create_kap_filing(
            title="Valid Filing",
            disclosure_index=999,
        )

        mock_provider.get_kap_filings.return_value = [filing_no_source, filing_with_source]

        with patch(
            "app.services.data.kap_data_service.get_provider_for_kap_filings",
            return_value=mock_provider
        ):
            result = await sync_kap_filings(db_session, "THYAO", filing_types=["FR"])

        # Should succeed but with warnings
        assert result.success is True
        assert len(result.validation_warnings) > 0
        # Only filing with source_url should be processed
        assert result.filings_processed == 1

    @pytest.mark.asyncio
    async def test_sync_rate_limit_does_not_consume_retry_budget(self, db_session, mock_provider, sample_kap_filings):
        """Rate limit waits should not consume retry attempts."""
        stock = Stock(symbol="THYAO", company_name="Test", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        rate_limit_error = ProviderRateLimitError("Slow down")
        rate_limit_error.retry_after = 0
        mock_provider.get_kap_filings.side_effect = [
            rate_limit_error,
            ProviderConnectionError("Connection failed"),
            sample_kap_filings,
        ]

        with patch(
            "app.services.data.kap_data_service.get_provider_for_kap_filings",
            return_value=mock_provider
        ):
            result = await sync_kap_filings(db_session, "THYAO", filing_types=["FR"], max_retries=2)

        assert result.success is True
        assert mock_provider.get_kap_filings.call_count == 3


# ============================================================================
# batch_sync_kap_filings Tests
# ============================================================================


class TestBatchSyncKapFilings:
    """Tests for batch_sync_kap_filings function."""

    @pytest.mark.asyncio
    async def test_batch_sync_creates_pipeline_log(self, db_session, mock_provider, sample_kap_filings):
        """Should create PipelineLog entry."""
        # Setup stocks
        for symbol in ["THYAO", "GARAN"]:
            stock = Stock(symbol=symbol, company_name=f"{symbol} Company", is_active=True)
            db_session.add(stock)
        await db_session.commit()

        mock_provider.get_kap_filings.return_value = sample_kap_filings

        with patch(
            "app.services.data.kap_data_service.get_provider_for_kap_filings",
            return_value=mock_provider
        ):
            result = await batch_sync_kap_filings(db_session, ["THYAO", "GARAN"], filing_types=["FR"])

        # Verify PipelineLog was created
        log_result = await db_session.execute(
            select(PipelineLog).where(PipelineLog.run_id == result.run_id)
        )
        log = log_result.scalar_one_or_none()

        assert log is not None
        assert log.pipeline_name == "kap_filings_sync"
        assert log.status == "success"

    @pytest.mark.asyncio
    async def test_batch_sync_partial_success(self, db_session, mock_provider, sample_kap_filings):
        """Partial success should have status='partial'."""
        # Setup stocks
        for symbol in ["THYAO", "GARAN"]:
            stock = Stock(symbol=symbol, company_name=f"{symbol} Company", is_active=True)
            db_session.add(stock)
        await db_session.commit()

        # THYAO succeeds, GARAN fails
        def mock_get_filings(symbol, **kwargs):
            if symbol == "THYAO":
                return sample_kap_filings
            raise ProviderSymbolNotFoundError(symbol)

        mock_provider.get_kap_filings.side_effect = mock_get_filings

        with patch(
            "app.services.data.kap_data_service.get_provider_for_kap_filings",
            return_value=mock_provider
        ):
            result = await batch_sync_kap_filings(db_session, ["THYAO", "GARAN"], filing_types=["FR"])

        assert result.status == "partial"
        assert "THYAO" in result.successful
        assert len(result.failed) == 1
        assert result.failed[0].symbol == "GARAN"

    @pytest.mark.asyncio
    async def test_batch_sync_all_failed(self, db_session, mock_provider):
        """All failed should have status='failed'."""
        # Setup stock
        stock = Stock(symbol="THYAO", company_name="Test", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        mock_provider.get_kap_filings.side_effect = ProviderConnectionError("Connection failed")

        with patch(
            "app.services.data.kap_data_service.get_provider_for_kap_filings",
            return_value=mock_provider
        ):
            result = await batch_sync_kap_filings(db_session, ["THYAO"], filing_types=["FR"])

        assert result.status == "failed"
        assert len(result.successful) == 0
        assert len(result.failed) == 1

    @pytest.mark.asyncio
    async def test_batch_sync_total_processed_count(self, db_session, mock_provider, sample_kap_filings):
        """Should count total processed records across all symbols."""
        # Setup stocks
        for symbol in ["THYAO", "GARAN"]:
            stock = Stock(symbol=symbol, company_name=f"{symbol} Company", is_active=True)
            db_session.add(stock)
        await db_session.commit()

        mock_provider.get_kap_filings.return_value = sample_kap_filings

        with patch(
            "app.services.data.kap_data_service.get_provider_for_kap_filings",
            return_value=mock_provider
        ):
            result = await batch_sync_kap_filings(db_session, ["THYAO", "GARAN"], filing_types=["FR"])

        # 5 filings per symbol * 2 symbols = 10 total
        assert result.total_processed == 10

    @pytest.mark.asyncio
    async def test_batch_sync_uses_default_filing_types(self, db_session, mock_provider, sample_kap_filings):
        """Should use default filing_types if not provided."""
        stock = Stock(symbol="THYAO", company_name="Test", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        mock_provider.get_kap_filings.return_value = sample_kap_filings

        with patch(
            "app.services.data.kap_data_service.get_provider_for_kap_filings",
            return_value=mock_provider
        ):
            result = await batch_sync_kap_filings(db_session, ["THYAO"])

        assert result.status == "success"
        # Verify default filing_types was used
        call_args = mock_provider.get_kap_filings.call_args
        assert call_args.kwargs.get("filing_types") == ["FR"]


# ============================================================================
# KapSyncResult Model Tests
# ============================================================================


class TestKapSyncResultModel:
    """Tests for KapSyncResult Pydantic model."""

    def test_default_values(self):
        """Should have correct default values."""
        result = KapSyncResult(symbol="THYAO", success=True)
        assert result.filings_processed == 0
        assert result.validation_warnings == []
        assert result.error_message is None
        assert result.duration_seconds is None

    def test_with_all_fields(self):
        """Should accept all fields."""
        result = KapSyncResult(
            symbol="THYAO",
            success=True,
            filings_processed=10,
            validation_warnings=["Missing pdf_url"],
            error_message=None,
            duration_seconds=1.5,
        )
        assert result.filings_processed == 10
        assert result.validation_warnings == ["Missing pdf_url"]
        assert result.duration_seconds == 1.5


class TestKapBatchSyncResultModel:
    """Tests for KapBatchSyncResult Pydantic model."""

    def test_default_status_values(self):
        """Status should be explicitly set."""
        result = KapBatchSyncResult(
            pipeline_name="test",
            run_id=str(uuid.uuid4()),
            status="success",
            started_at=datetime.now(),
            finished_at=datetime.now(),
            total_processed=10,
            successful=["THYAO"],
            failed=[],
        )
        assert result.status == "success"
        assert result.details is None