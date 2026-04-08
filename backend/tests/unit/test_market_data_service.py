"""Unit tests for market_data_service.

Tests the service layer with mocked providers and database operations.
"""

import pytest
from datetime import date, datetime
from unittest.mock import AsyncMock, patch, MagicMock
import uuid

from sqlalchemy import select

from app.models.stock import Stock
from app.models.pipeline_log import PipelineLog
from app.services.data.market_data_service import (
    SyncResult,
    BatchSyncResult,
    sync_price_history,
    batch_sync_prices,
    get_active_stocks,
)
from app.services.data.provider_exceptions import (
    ProviderConnectionError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderSymbolNotFoundError,
    ProviderDataNotFoundError,
)
from tests.factories import create_price_bar, create_price_bars_batch


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_provider():
    """Create a mock provider for testing."""
    provider = MagicMock()
    provider.get_price_history = MagicMock()
    return provider


@pytest.fixture
def sample_price_bars():
    """Create sample price bars for testing."""
    return create_price_bars_batch(symbol="THYAO", num_bars=10)


# ============================================================================
# sync_price_history Tests
# ============================================================================


class TestSyncPriceHistory:
    """Tests for sync_price_history function."""

    @pytest.mark.asyncio
    async def test_sync_success_returns_result(self, db_session, mock_provider, sample_price_bars):
        """Successful sync should return SyncResult with count."""
        # Setup: Create stock in database
        stock = Stock(symbol="THYAO", company_name="Test Stock", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        # Mock provider to return price bars
        mock_provider.get_price_history.return_value = sample_price_bars

        with patch(
            "app.services.data.market_data_service.get_provider_for_prices",
            return_value=mock_provider
        ):
            result = await sync_price_history(db_session, "THYAO", period="1y")

        assert result.success is True
        assert result.symbol == "THYAO"
        assert result.records_processed == 10
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_sync_handles_stock_not_found(self, db_session, mock_provider):
        """Should return failed result for unknown symbol."""
        # No stock in database

        with patch(
            "app.services.data.market_data_service.get_provider_for_prices",
            return_value=mock_provider
        ):
            result = await sync_price_history(db_session, "INVALID", period="1y")

        assert result.success is False
        assert result.symbol == "INVALID"
        assert "not found" in result.error_message.lower()
        # Provider should not be called
        mock_provider.get_price_history.assert_not_called()

    @pytest.mark.asyncio
    async def test_sync_handles_empty_data(self, db_session, mock_provider):
        """Empty price data should succeed with 0 records."""
        # Setup stock
        stock = Stock(symbol="THYAO", company_name="Test Stock", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        # Mock provider to return empty list
        mock_provider.get_price_history.return_value = []

        with patch(
            "app.services.data.market_data_service.get_provider_for_prices",
            return_value=mock_provider
        ):
            result = await sync_price_history(db_session, "THYAO", period="1y")

        assert result.success is True
        assert result.records_processed == 0

    @pytest.mark.asyncio
    async def test_sync_handles_provider_symbol_not_found(self, db_session, mock_provider):
        """ProviderSymbolNotFoundError should return failed result."""
        stock = Stock(symbol="INVALID", company_name="Test", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        mock_provider.get_price_history.side_effect = ProviderSymbolNotFoundError("INVALID")

        with patch(
            "app.services.data.market_data_service.get_provider_for_prices",
            return_value=mock_provider
        ):
            result = await sync_price_history(db_session, "INVALID", period="1y")

        assert result.success is False
        assert "not found" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_sync_handles_provider_data_not_found(self, db_session, mock_provider):
        """ProviderDataNotFoundError should succeed with 0 records."""
        stock = Stock(symbol="THYAO", company_name="Test", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        mock_provider.get_price_history.side_effect = ProviderDataNotFoundError("No data")

        with patch(
            "app.services.data.market_data_service.get_provider_for_prices",
            return_value=mock_provider
        ):
            result = await sync_price_history(db_session, "THYAO", period="1y")

        assert result.success is True
        assert result.records_processed == 0

    @pytest.mark.asyncio
    async def test_sync_retries_on_connection_error(self, db_session, mock_provider, sample_price_bars):
        """Should retry on ProviderConnectionError."""
        stock = Stock(symbol="THYAO", company_name="Test", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        # Fail twice, succeed on third try
        mock_provider.get_price_history.side_effect = [
            ProviderConnectionError("Connection failed"),
            ProviderConnectionError("Connection failed"),
            sample_price_bars,
        ]

        with patch(
            "app.services.data.market_data_service.get_provider_for_prices",
            return_value=mock_provider
        ):
            result = await sync_price_history(db_session, "THYAO", period="1y", max_retries=3)

        assert result.success is True
        assert result.records_processed == 10
        assert mock_provider.get_price_history.call_count == 3

    @pytest.mark.asyncio
    async def test_sync_fails_after_max_retries(self, db_session, mock_provider):
        """Should fail after max retries exceeded."""
        stock = Stock(symbol="THYAO", company_name="Test", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        # Always fail
        mock_provider.get_price_history.side_effect = ProviderConnectionError("Connection failed")

        with patch(
            "app.services.data.market_data_service.get_provider_for_prices",
            return_value=mock_provider
        ):
            result = await sync_price_history(db_session, "THYAO", period="1y", max_retries=3)

        assert result.success is False
        assert "retries" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_sync_normalizes_symbol(self, db_session, mock_provider, sample_price_bars):
        """Symbol should be normalized to uppercase."""
        stock = Stock(symbol="THYAO", company_name="Test", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        mock_provider.get_price_history.return_value = sample_price_bars

        with patch(
            "app.services.data.market_data_service.get_provider_for_prices",
            return_value=mock_provider
        ):
            result = await sync_price_history(db_session, "thyao", period="1y")

        assert result.symbol == "THYAO"
        # Verify provider was called with uppercase symbol
        mock_provider.get_price_history.assert_called_once()
        call_args = mock_provider.get_price_history.call_args
        assert call_args[0][0] == "THYAO"

    @pytest.mark.asyncio
    async def test_rate_limit_does_not_consume_retry_budget(self, db_session, mock_provider, sample_price_bars):
        """Rate limit waits should not consume retry attempts."""
        stock = Stock(symbol="THYAO", company_name="Test", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        rate_limit_error = ProviderRateLimitError("Slow down")
        rate_limit_error.retry_after = 0
        mock_provider.get_price_history.side_effect = [
            rate_limit_error,
            ProviderConnectionError("Connection failed"),
            sample_price_bars,
        ]

        with patch(
            "app.services.data.market_data_service.get_provider_for_prices",
            return_value=mock_provider
        ):
            result = await sync_price_history(db_session, "THYAO", period="1y", max_retries=2)

        assert result.success is True
        assert mock_provider.get_price_history.call_count == 3


# ============================================================================
# batch_sync_prices Tests
# ============================================================================


class TestBatchSyncPrices:
    """Tests for batch_sync_prices function."""

    @pytest.mark.asyncio
    async def test_batch_sync_creates_pipeline_log(self, db_session, mock_provider, sample_price_bars):
        """Should create PipelineLog entry."""
        # Setup stocks
        for symbol in ["THYAO", "GARAN"]:
            stock = Stock(symbol=symbol, company_name=f"{symbol} Company", is_active=True)
            db_session.add(stock)
        await db_session.commit()

        mock_provider.get_price_history.return_value = sample_price_bars

        with patch(
            "app.services.data.market_data_service.get_provider_for_prices",
            return_value=mock_provider
        ):
            result = await batch_sync_prices(db_session, ["THYAO", "GARAN"], period="1y")

        # Verify PipelineLog was created
        log_result = await db_session.execute(
            select(PipelineLog).where(PipelineLog.run_id == result.run_id)
        )
        log = log_result.scalar_one_or_none()

        assert log is not None
        assert log.pipeline_name == "price_sync"
        assert log.status == "success"

    @pytest.mark.asyncio
    async def test_batch_sync_partial_success(self, db_session, mock_provider, sample_price_bars):
        """Partial success should have status='partial'."""
        # Setup stocks
        for symbol in ["THYAO", "GARAN"]:
            stock = Stock(symbol=symbol, company_name=f"{symbol} Company", is_active=True)
            db_session.add(stock)
        await db_session.commit()

        # THYAO succeeds, GARAN fails
        def mock_get_history(symbol, **kwargs):
            if symbol == "THYAO":
                return sample_price_bars
            raise ProviderSymbolNotFoundError(symbol)

        mock_provider.get_price_history.side_effect = mock_get_history

        with patch(
            "app.services.data.market_data_service.get_provider_for_prices",
            return_value=mock_provider
        ):
            result = await batch_sync_prices(db_session, ["THYAO", "GARAN"], period="1y")

        assert result.status == "partial"
        assert "THYAO" in result.successful
        assert len(result.failed) == 1
        assert result.failed[0].symbol == "GARAN"

    @pytest.mark.asyncio
    async def test_batch_sync_all_failed(self, db_session, mock_provider):
        """All failed should have status='failed'."""
        # Setup stocks
        stock = Stock(symbol="THYAO", company_name="Test", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        mock_provider.get_price_history.side_effect = ProviderConnectionError("Connection failed")

        with patch(
            "app.services.data.market_data_service.get_provider_for_prices",
            return_value=mock_provider
        ):
            result = await batch_sync_prices(db_session, ["THYAO"], period="1y")

        assert result.status == "failed"
        assert len(result.successful) == 0
        assert len(result.failed) == 1

    @pytest.mark.asyncio
    async def test_batch_sync_total_processed_count(self, db_session, mock_provider, sample_price_bars):
        """Should count total processed records across all symbols."""
        # Setup stocks
        for symbol in ["THYAO", "GARAN"]:
            stock = Stock(symbol=symbol, company_name=f"{symbol} Company", is_active=True)
            db_session.add(stock)
        await db_session.commit()

        mock_provider.get_price_history.return_value = sample_price_bars

        with patch(
            "app.services.data.market_data_service.get_provider_for_prices",
            return_value=mock_provider
        ):
            result = await batch_sync_prices(db_session, ["THYAO", "GARAN"], period="1y")

        # 10 bars per symbol * 2 symbols = 20 total
        assert result.total_processed == 20


# ============================================================================
# get_active_stocks Tests
# ============================================================================


class TestGetActiveStocks:
    """Tests for get_active_stocks function."""

    @pytest.mark.asyncio
    async def test_returns_active_symbols(self, db_session):
        """Should return list of active stock symbols."""
        # Create active stocks
        for symbol in ["THYAO", "GARAN", "ASELS"]:
            stock = Stock(symbol=symbol, company_name=f"{symbol} Company", is_active=True)
            db_session.add(stock)

        # Create inactive stock
        inactive = Stock(symbol="INACTIVE", company_name="Inactive", is_active=False)
        db_session.add(inactive)
        await db_session.commit()

        result = await get_active_stocks(db_session)

        assert len(result) == 3
        assert "THYAO" in result
        assert "GARAN" in result
        assert "ASELS" in result
        assert "INACTIVE" not in result

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_stocks(self, db_session):
        """Should return empty list when no stocks exist."""
        result = await get_active_stocks(db_session)
        assert result == []


# ============================================================================
# SyncResult Model Tests
# ============================================================================


class TestSyncResultModel:
    """Tests for SyncResult Pydantic model."""

    def test_default_values(self):
        """Should have correct default values."""
        result = SyncResult(symbol="THYAO", success=True)
        assert result.records_processed == 0
        assert result.error_message is None
        assert result.duration_seconds is None

    def test_with_all_fields(self):
        """Should accept all fields."""
        result = SyncResult(
            symbol="THYAO",
            success=True,
            records_processed=100,
            error_message=None,
            duration_seconds=1.5,
        )
        assert result.records_processed == 100
        assert result.duration_seconds == 1.5


class TestBatchSyncResultModel:
    """Tests for BatchSyncResult Pydantic model."""

    def test_default_status_values(self):
        """Status should be explicitly set."""
        result = BatchSyncResult(
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
