"""Unit tests for stock_service module."""

import pytest
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stock import Stock
from app.models.stock_price import StockPrice
from app.services.stock_service import (
    get_all_stocks,
    get_stock_by_symbol,
    get_price_history,
)


class TestGetAllStocks:
    """Tests for get_all_stocks function."""

    @pytest.mark.asyncio
    async def test_returns_all_active_stocks(self, db_session: AsyncSession):
        """Should return all active stocks when no filter."""
        # Create test stocks
        stock1 = Stock(symbol="THYAO", company_name="Turk Hava", sector="Transportation", is_active=True)
        stock2 = Stock(symbol="GARAN", company_name="Garanti", sector="Finance", is_active=True)
        stock3 = Stock(symbol="SAHOL", company_name="Sabanci", sector="Conglomerates", is_active=True)
        db_session.add_all([stock1, stock2, stock3])
        await db_session.commit()

        result = await get_all_stocks(db_session)
        assert len(result) == 3
        symbols = [s.symbol for s in result]
        assert "THYAO" in symbols
        assert "GARAN" in symbols
        assert "SAHOL" in symbols

    @pytest.mark.asyncio
    async def test_filters_by_symbol_search(self, db_session: AsyncSession):
        """Should filter stocks by symbol substring."""
        # Create test stocks
        stock1 = Stock(symbol="THYAO", company_name="Turk Hava", sector="Transportation", is_active=True)
        stock2 = Stock(symbol="GARAN", company_name="Garanti", sector="Finance", is_active=True)
        stock3 = Stock(symbol="THYAO.IS", company_name="THYAO IS", sector="Transportation", is_active=True)
        db_session.add_all([stock1, stock2, stock3])
        await db_session.commit()

        # Search for THY
        result = await get_all_stocks(db_session, search="THY")
        assert len(result) == 2
        symbols = [s.symbol for s in result]
        assert all("THY" in s for s in symbols)

    @pytest.mark.asyncio
    async def test_excludes_inactive_stocks(self, db_session: AsyncSession):
        """Should exclude inactive stocks."""
        stock1 = Stock(symbol="THYAO", company_name="Turk Hava", sector="Transportation", is_active=True)
        stock2 = Stock(symbol="INACTIVE", company_name="Inactive", sector="Test", is_active=False)
        db_session.add_all([stock1, stock2])
        await db_session.commit()

        result = await get_all_stocks(db_session)
        assert len(result) == 1
        assert result[0].symbol == "THYAO"

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_stocks(self, db_session: AsyncSession):
        """Should return empty list when no stocks exist."""
        result = await get_all_stocks(db_session)
        assert result == []

    @pytest.mark.asyncio
    async def test_search_case_insensitive(self, db_session: AsyncSession):
        """Search should be case insensitive."""
        stock = Stock(symbol="THYAO", company_name="Turk Hava", sector="Transportation", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        # Search with lowercase
        result = await get_all_stocks(db_session, search="thyao")
        assert len(result) == 1

        # Search with uppercase
        result = await get_all_stocks(db_session, search="THYAO")
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_returns_ordered_by_symbol(self, db_session: AsyncSession):
        """Should return stocks ordered by symbol ascending."""
        stock1 = Stock(symbol="YKBNK", company_name="Yapi Kredi", sector="Finance", is_active=True)
        stock2 = Stock(symbol="AKBNK", company_name="Akbank", sector="Finance", is_active=True)
        stock3 = Stock(symbol="GARAN", company_name="Garanti", sector="Finance", is_active=True)
        db_session.add_all([stock1, stock2, stock3])
        await db_session.commit()

        result = await get_all_stocks(db_session)
        symbols = [s.symbol for s in result]
        assert symbols == ["AKBNK", "GARAN", "YKBNK"]


class TestGetStockBySymbol:
    """Tests for get_stock_by_symbol function."""

    @pytest.mark.asyncio
    async def test_returns_stock_when_found(self, db_session: AsyncSession):
        """Should return stock when symbol exists."""
        stock = Stock(symbol="THYAO", company_name="Turk Hava", sector="Transportation", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        result = await get_stock_by_symbol(db_session, "THYAO")
        assert result is not None
        assert result.symbol == "THYAO"
        assert result.company_name == "Turk Hava"

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self, db_session: AsyncSession):
        """Should return None when symbol not found."""
        result = await get_stock_by_symbol(db_session, "NOTEXIST")
        assert result is None

    @pytest.mark.asyncio
    async def test_normalizes_symbol_to_uppercase(self, db_session: AsyncSession):
        """Should normalize symbol to uppercase."""
        stock = Stock(symbol="THYAO", company_name="Turk Hava", sector="Transportation", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        result = await get_stock_by_symbol(db_session, "thyao")
        assert result is not None
        assert result.symbol == "THYAO"


class TestGetPriceHistory:
    """Tests for get_price_history function."""

    @pytest.mark.asyncio
    async def test_returns_price_history(self, db_session: AsyncSession):
        """Should return price history for stock."""
        # Create stock
        stock = Stock(symbol="THYAO", company_name="Turk Hava", sector="Transportation", is_active=True)
        db_session.add(stock)
        await db_session.commit()
        await db_session.refresh(stock)

        # Create price bars
        price1 = StockPrice(stock_id=stock.id, date=date(2024, 1, 1), open=100.0, high=105.0, low=99.0, close=102.0, volume=1000)
        price2 = StockPrice(stock_id=stock.id, date=date(2024, 1, 2), open=102.0, high=107.0, low=101.0, close=105.0, volume=1200)
        price3 = StockPrice(stock_id=stock.id, date=date(2024, 1, 3), open=105.0, high=110.0, low=104.0, close=108.0, volume=1500)
        db_session.add_all([price1, price2, price3])
        await db_session.commit()

        result = await get_price_history(db_session, "THYAO")
        assert len(result) == 3
        assert result[0].date == date(2024, 1, 1)
        assert result[2].close == 108.0

    @pytest.mark.asyncio
    async def test_filters_by_start_date(self, db_session: AsyncSession):
        """Should filter by start_date."""
        # Create stock
        stock = Stock(symbol="THYAO", company_name="Turk Hava", sector="Transportation", is_active=True)
        db_session.add(stock)
        await db_session.commit()
        await db_session.refresh(stock)

        # Create price bars
        price1 = StockPrice(stock_id=stock.id, date=date(2024, 1, 1), close=100.0)
        price2 = StockPrice(stock_id=stock.id, date=date(2024, 1, 15), close=105.0)
        price3 = StockPrice(stock_id=stock.id, date=date(2024, 2, 1), close=110.0)
        db_session.add_all([price1, price2, price3])
        await db_session.commit()

        result = await get_price_history(db_session, "THYAO", start_date=date(2024, 1, 10))
        assert len(result) == 2
        dates = [p.date for p in result]
        assert date(2024, 1, 1) not in dates
        assert date(2024, 1, 15) in dates
        assert date(2024, 2, 1) in dates

    @pytest.mark.asyncio
    async def test_filters_by_end_date(self, db_session: AsyncSession):
        """Should filter by end_date."""
        # Create stock
        stock = Stock(symbol="THYAO", company_name="Turk Hava", sector="Transportation", is_active=True)
        db_session.add(stock)
        await db_session.commit()
        await db_session.refresh(stock)

        # Create price bars
        price1 = StockPrice(stock_id=stock.id, date=date(2024, 1, 1), close=100.0)
        price2 = StockPrice(stock_id=stock.id, date=date(2024, 1, 15), close=105.0)
        price3 = StockPrice(stock_id=stock.id, date=date(2024, 2, 1), close=110.0)
        db_session.add_all([price1, price2, price3])
        await db_session.commit()

        result = await get_price_history(db_session, "THYAO", end_date=date(2024, 1, 20))
        assert len(result) == 2
        dates = [p.date for p in result]
        assert date(2024, 1, 1) in dates
        assert date(2024, 1, 15) in dates
        assert date(2024, 2, 1) not in dates

    @pytest.mark.asyncio
    async def test_returns_empty_when_stock_not_found(self, db_session: AsyncSession):
        """Should return empty list when stock not found."""
        result = await get_price_history(db_session, "NOTEXIST")
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_ordered_by_date_asc(self, db_session: AsyncSession):
        """Should return prices ordered by date ascending."""
        # Create stock
        stock = Stock(symbol="THYAO", company_name="Turk Hava", sector="Transportation", is_active=True)
        db_session.add(stock)
        await db_session.commit()
        await db_session.refresh(stock)

        # Create price bars in reverse order
        price1 = StockPrice(stock_id=stock.id, date=date(2024, 3, 1), close=120.0)
        price2 = StockPrice(stock_id=stock.id, date=date(2024, 1, 1), close=100.0)
        price3 = StockPrice(stock_id=stock.id, date=date(2024, 2, 1), close=110.0)
        db_session.add_all([price1, price2, price3])
        await db_session.commit()

        result = await get_price_history(db_session, "THYAO")
        dates = [p.date for p in result]
        assert dates == [date(2024, 1, 1), date(2024, 2, 1), date(2024, 3, 1)]