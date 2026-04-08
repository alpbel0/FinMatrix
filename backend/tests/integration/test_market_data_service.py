"""Integration tests for market_data_service.

Tests with real database session but mocked provider.
"""

import pytest
from datetime import date, timedelta
from unittest.mock import patch, MagicMock

from sqlalchemy import select

from app.models.stock import Stock
from app.models.stock_price import StockPrice
from app.models.pipeline_log import PipelineLog
from app.services.data.market_data_service import (
    sync_price_history,
    batch_sync_prices,
    get_active_stocks,
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


# ============================================================================
# sync_price_history Integration Tests
# ============================================================================


class TestSyncPriceHistoryIntegration:
    """Integration tests for sync_price_history with real database."""

    @pytest.mark.asyncio
    async def test_sync_persists_to_database(self, db_session, mock_provider):
        """Synced price bars should persist to stock_prices table."""
        # Create stock
        stock = Stock(symbol="THYAO", company_name="Turk Hava Yollari", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        # Create price bars
        bars = create_price_bars_batch(
            symbol="THYAO",
            num_bars=10,
            start_date=date.today() - timedelta(days=10),
        )
        mock_provider.get_price_history.return_value = bars

        with patch(
            "app.services.data.market_data_service.get_provider_for_prices",
            return_value=mock_provider
        ):
            result = await sync_price_history(db_session, "THYAO", period="1y")

        assert result.success is True
        assert result.records_processed == 10

        # Verify data persisted
        db_result = await db_session.execute(
            select(StockPrice).where(StockPrice.stock_id == stock.id)
        )
        db_prices = list(db_result.scalars().all())

        assert len(db_prices) == 10
        # Verify OHLCV values persisted correctly
        for db_price in db_prices:
            assert db_price.close is not None
            assert db_price.volume is not None

    @pytest.mark.asyncio
    async def test_sync_upsert_updates_existing_prices(self, db_session, mock_provider):
        """Upsert should update existing price records."""
        # Create stock
        stock = Stock(symbol="THYAO", company_name="Test", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        # First sync
        bars_v1 = [create_price_bar(date_val=date.today(), close=100.0)]
        mock_provider.get_price_history.return_value = bars_v1

        with patch(
            "app.services.data.market_data_service.get_provider_for_prices",
            return_value=mock_provider
        ):
            await sync_price_history(db_session, "THYAO")

        # Second sync with updated price
        bars_v2 = [create_price_bar(date_val=date.today(), close=150.0)]
        mock_provider.get_price_history.return_value = bars_v2

        with patch(
            "app.services.data.market_data_service.get_provider_for_prices",
            return_value=mock_provider
        ):
            await sync_price_history(db_session, "THYAO")

        # Verify only one record exists with updated value
        db_result = await db_session.execute(
            select(StockPrice).where(StockPrice.stock_id == stock.id)
        )
        db_prices = list(db_result.scalars().all())

        assert len(db_prices) == 1
        assert db_prices[0].close == 150.0

    @pytest.mark.asyncio
    async def test_sync_multiple_stocks(self, db_session, mock_provider):
        """Should handle syncing multiple stocks independently."""
        # Create stocks
        for symbol in ["THYAO", "GARAN", "ASELS"]:
            stock = Stock(symbol=symbol, company_name=f"{symbol} Company", is_active=True)
            db_session.add(stock)
        await db_session.commit()

        bars = create_price_bars_batch(symbol="TEST", num_bars=5)
        mock_provider.get_price_history.return_value = bars

        with patch(
            "app.services.data.market_data_service.get_provider_for_prices",
            return_value=mock_provider
        ):
            for symbol in ["THYAO", "GARAN", "ASELS"]:
                result = await sync_price_history(db_session, symbol)
                assert result.success is True

        # Verify each stock has its own prices
        for symbol in ["THYAO", "GARAN", "ASELS"]:
            stock_result = await db_session.execute(
                select(Stock).where(Stock.symbol == symbol)
            )
            stock = stock_result.scalar_one()
            price_result = await db_session.execute(
                select(StockPrice).where(StockPrice.stock_id == stock.id)
            )
            prices = list(price_result.scalars().all())
            assert len(prices) == 5


# ============================================================================
# batch_sync_prices Integration Tests
# ============================================================================


class TestBatchSyncPricesIntegration:
    """Integration tests for batch_sync_prices with real database."""

    @pytest.mark.asyncio
    async def test_batch_sync_pipeline_log_persists(self, db_session, mock_provider):
        """PipelineLog should be persisted with correct details."""
        # Create stocks
        for symbol in ["THYAO", "GARAN"]:
            stock = Stock(symbol=symbol, company_name=f"{symbol} Company", is_active=True)
            db_session.add(stock)
        await db_session.commit()

        bars = create_price_bars_batch(symbol="TEST", num_bars=10)
        mock_provider.get_price_history.return_value = bars

        with patch(
            "app.services.data.market_data_service.get_provider_for_prices",
            return_value=mock_provider
        ):
            result = await batch_sync_prices(
                db_session, ["THYAO", "GARAN"], period="1y"
            )

        # Verify PipelineLog persisted
        log_result = await db_session.execute(
            select(PipelineLog).where(PipelineLog.run_id == result.run_id)
        )
        saved_log = log_result.scalar_one()

        assert saved_log.pipeline_name == "price_sync"
        assert saved_log.status == "success"
        assert saved_log.processed_count == 20  # 10 bars * 2 symbols
        assert saved_log.details["period"] == "1y"
        assert "THYAO" in saved_log.details["successful_symbols"]
        assert "GARAN" in saved_log.details["successful_symbols"]

    @pytest.mark.asyncio
    async def test_batch_sync_partial_logs_failures(self, db_session, mock_provider):
        """Partial failure should log failed symbols."""
        # Create stocks
        for symbol in ["THYAO", "GARAN", "INVALID"]:
            stock = Stock(symbol=symbol, company_name=f"{symbol} Company", is_active=True)
            db_session.add(stock)
        await db_session.commit()

        bars = create_price_bars_batch(symbol="TEST", num_bars=5)

        def mock_get_history(symbol, **kwargs):
            if symbol == "INVALID":
                raise Exception("Provider error")
            return bars

        mock_provider.get_price_history.side_effect = mock_get_history

        with patch(
            "app.services.data.market_data_service.get_provider_for_prices",
            return_value=mock_provider
        ):
            result = await batch_sync_prices(
                db_session, ["THYAO", "GARAN", "INVALID"], period="1y"
            )

        assert result.status == "partial"

        # Verify log contains failure info
        log_result = await db_session.execute(
            select(PipelineLog).where(PipelineLog.run_id == result.run_id)
        )
        saved_log = log_result.scalar_one()

        assert "INVALID" in saved_log.details["failed_symbols"]
        assert saved_log.error_message is not None


# ============================================================================
# get_active_stocks Integration Tests
# ============================================================================


class TestGetActiveStocksIntegration:
    """Integration tests for get_active_stocks with real database."""

    @pytest.mark.asyncio
    async def test_returns_only_active_stocks(self, db_session):
        """Should return only stocks where is_active=True."""
        # Create active and inactive stocks
        active_stocks = [
            Stock(symbol="THYAO", company_name="Active 1", is_active=True),
            Stock(symbol="GARAN", company_name="Active 2", is_active=True),
        ]
        inactive_stock = Stock(symbol="INACTIVE", company_name="Inactive", is_active=False)

        for stock in active_stocks + [inactive_stock]:
            db_session.add(stock)
        await db_session.commit()

        result = await get_active_stocks(db_session)

        assert len(result) == 2
        assert "THYAO" in result
        assert "GARAN" in result
        assert "INACTIVE" not in result

    @pytest.mark.asyncio
    async def test_empty_result_when_no_stocks(self, db_session):
        """Should return empty list when no stocks exist."""
        result = await get_active_stocks(db_session)
        assert result == []


# ============================================================================
# End-to-End Price Sync Flow Tests
# ============================================================================


class TestPriceSyncEndToEnd:
    """End-to-end tests for price sync flow."""

    @pytest.mark.asyncio
    async def test_full_sync_flow(self, db_session, mock_provider):
        """Test complete sync flow from stock creation to database persistence."""
        # Step 1: Create stock
        stock = Stock(symbol="THYAO", company_name="Turk Hava Yollari", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        # Step 2: Prepare mock data
        today = date.today()
        bars = [
            create_price_bar(date_val=today - timedelta(days=i), close=100.0 + i)
            for i in range(365)  # 1 year of data
        ]
        mock_provider.get_price_history.return_value = bars

        # Step 3: Run sync
        with patch(
            "app.services.data.market_data_service.get_provider_for_prices",
            return_value=mock_provider
        ):
            result = await sync_price_history(db_session, "THYAO", period="1y")

        # Step 4: Verify results
        assert result.success is True
        assert result.records_processed == 365

        # Step 5: Verify database state
        db_result = await db_session.execute(
            select(StockPrice)
            .where(StockPrice.stock_id == stock.id)
            .order_by(StockPrice.date)
        )
        db_prices = list(db_result.scalars().all())

        assert len(db_prices) == 365
        # First bar should be oldest
        assert db_prices[0].date == today - timedelta(days=364)
        # Last bar should be newest
        assert db_prices[-1].date == today