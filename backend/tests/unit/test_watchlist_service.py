"""Unit tests for watchlist_service module."""

import pytest
from datetime import date, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stock import Stock
from app.models.stock_price import StockPrice
from app.models.user import User
from app.models.watchlist import Watchlist
from app.services.watchlist_service import (
    add_to_watchlist,
    get_latest_price_for_stock,
    get_previous_price_for_stock,
    get_user_watchlist,
    remove_from_watchlist,
    toggle_notifications,
)


class TestGetUserWatchlist:
    """Tests for get_user_watchlist function."""

    @pytest.mark.asyncio
    async def test_returns_user_watchlist_items(self, db_session: AsyncSession):
        """Should return watchlist items for user with stock loaded."""
        # Create user and stocks
        user = User(username="testuser", email="test@example.com", password_hash="hash")
        stock1 = Stock(symbol="THYAO", company_name="Turk Hava", sector="Transportation", is_active=True)
        stock2 = Stock(symbol="GARAN", company_name="Garanti", sector="Finance", is_active=True)
        db_session.add_all([user, stock1, stock2])
        await db_session.commit()

        # Create watchlist items
        wl1 = Watchlist(user_id=user.id, stock_id=stock1.id, notifications_enabled=True)
        wl2 = Watchlist(user_id=user.id, stock_id=stock2.id, notifications_enabled=False)
        db_session.add_all([wl1, wl2])
        await db_session.commit()

        result = await get_user_watchlist(db_session, user.id)

        assert len(result) == 2
        symbols = [item.stock.symbol for item in result]
        assert "THYAO" in symbols
        assert "GARAN" in symbols

    @pytest.mark.asyncio
    async def test_returns_empty_list_for_user_with_no_watchlist(self, db_session: AsyncSession):
        """Should return empty list when user has no watchlist items."""
        user = User(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        await db_session.commit()

        result = await get_user_watchlist(db_session, user.id)

        assert result == []

    @pytest.mark.asyncio
    async def test_does_not_return_other_users_items(self, db_session: AsyncSession):
        """Should only return items for specified user."""
        user1 = User(username="user1", email="user1@example.com", password_hash="hash")
        user2 = User(username="user2", email="user2@example.com", password_hash="hash")
        stock = Stock(symbol="THYAO", company_name="Turk Hava", is_active=True)
        db_session.add_all([user1, user2, stock])
        await db_session.commit()

        # Create watchlist for user2 only
        wl = Watchlist(user_id=user2.id, stock_id=stock.id)
        db_session.add(wl)
        await db_session.commit()

        result = await get_user_watchlist(db_session, user1.id)

        assert result == []


class TestGetLatestPriceForStock:
    """Tests for get_latest_price_for_stock function."""

    @pytest.mark.asyncio
    async def test_returns_latest_price(self, db_session: AsyncSession):
        """Should return the most recent price record."""
        stock = Stock(symbol="THYAO", company_name="Turk Hava", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        # Create multiple prices
        price1 = StockPrice(stock_id=stock.id, date=date(2026, 1, 1), close=100.0)
        price2 = StockPrice(stock_id=stock.id, date=date(2026, 1, 2), close=105.0)
        price3 = StockPrice(stock_id=stock.id, date=date(2026, 1, 3), close=110.0)
        db_session.add_all([price1, price2, price3])
        await db_session.commit()

        result = await get_latest_price_for_stock(db_session, stock.id)

        assert result is not None
        assert result.close == 110.0
        assert result.date == date(2026, 1, 3)

    @pytest.mark.asyncio
    async def test_returns_none_when_no_prices(self, db_session: AsyncSession):
        """Should return None when stock has no price records."""
        stock = Stock(symbol="THYAO", company_name="Turk Hava", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        result = await get_latest_price_for_stock(db_session, stock.id)

        assert result is None


class TestGetPreviousPriceForStock:
    """Tests for get_previous_price_for_stock function."""

    @pytest.mark.asyncio
    async def test_returns_previous_trading_day_price(self, db_session: AsyncSession):
        """Should return price before the current date."""
        stock = Stock(symbol="THYAO", company_name="Turk Hava", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        price1 = StockPrice(stock_id=stock.id, date=date(2026, 1, 1), close=100.0)
        price2 = StockPrice(stock_id=stock.id, date=date(2026, 1, 2), close=105.0)
        price3 = StockPrice(stock_id=stock.id, date=date(2026, 1, 3), close=110.0)
        db_session.add_all([price1, price2, price3])
        await db_session.commit()

        result = await get_previous_price_for_stock(db_session, stock.id, date(2026, 1, 3))

        assert result is not None
        assert result.close == 105.0
        assert result.date == date(2026, 1, 2)

    @pytest.mark.asyncio
    async def test_returns_none_when_no_previous_price(self, db_session: AsyncSession):
        """Should return None when no price exists before current date."""
        stock = Stock(symbol="THYAO", company_name="Turk Hava", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        price = StockPrice(stock_id=stock.id, date=date(2026, 1, 1), close=100.0)
        db_session.add(price)
        await db_session.commit()

        result = await get_previous_price_for_stock(db_session, stock.id, date(2026, 1, 1))

        assert result is None


class TestAddToWatchlist:
    """Tests for add_to_watchlist function."""

    @pytest.mark.asyncio
    async def test_creates_watchlist_item(self, db_session: AsyncSession):
        """Should create and return watchlist item."""
        user = User(username="testuser", email="test@example.com", password_hash="hash")
        stock = Stock(symbol="THYAO", company_name="Turk Hava", is_active=True)
        db_session.add_all([user, stock])
        await db_session.commit()

        result = await add_to_watchlist(db_session, user.id, stock.id, notifications_enabled=True)

        assert result.id is not None
        assert result.user_id == user.id
        assert result.stock_id == stock.id
        assert result.notifications_enabled is True

    @pytest.mark.asyncio
    async def test_creates_with_default_notifications(self, db_session: AsyncSession):
        """Should default notifications_enabled to True."""
        user = User(username="testuser", email="test@example.com", password_hash="hash")
        stock = Stock(symbol="THYAO", company_name="Turk Hava", is_active=True)
        db_session.add_all([user, stock])
        await db_session.commit()

        result = await add_to_watchlist(db_session, user.id, stock.id)

        assert result.notifications_enabled is True


class TestRemoveFromWatchlist:
    """Tests for remove_from_watchlist function."""

    @pytest.mark.asyncio
    async def test_removes_item_when_owned_by_user(self, db_session: AsyncSession):
        """Should remove and return True when user owns the item."""
        user = User(username="testuser", email="test@example.com", password_hash="hash")
        stock = Stock(symbol="THYAO", company_name="Turk Hava", is_active=True)
        db_session.add_all([user, stock])
        await db_session.commit()

        wl = Watchlist(user_id=user.id, stock_id=stock.id)
        db_session.add(wl)
        await db_session.commit()

        result = await remove_from_watchlist(db_session, wl.id, user.id)

        assert result is True
        # Verify deleted
        remaining = await db_session.get(Watchlist, wl.id)
        assert remaining is None

    @pytest.mark.asyncio
    async def test_returns_false_when_not_found(self, db_session: AsyncSession):
        """Should return False when item doesn't exist."""
        user = User(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        await db_session.commit()

        result = await remove_from_watchlist(db_session, 999, user.id)

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_when_not_owned(self, db_session: AsyncSession):
        """Should return False when item belongs to another user."""
        user1 = User(username="user1", email="user1@example.com", password_hash="hash")
        user2 = User(username="user2", email="user2@example.com", password_hash="hash")
        stock = Stock(symbol="THYAO", company_name="Turk Hava", is_active=True)
        db_session.add_all([user1, user2, stock])
        await db_session.commit()

        wl = Watchlist(user_id=user2.id, stock_id=stock.id)
        db_session.add(wl)
        await db_session.commit()

        result = await remove_from_watchlist(db_session, wl.id, user1.id)

        assert result is False
        # Verify not deleted
        remaining = await db_session.get(Watchlist, wl.id)
        assert remaining is not None


class TestToggleNotifications:
    """Tests for toggle_notifications function."""

    @pytest.mark.asyncio
    async def test_updates_notifications(self, db_session: AsyncSession):
        """Should update notifications_enabled field."""
        user = User(username="testuser", email="test@example.com", password_hash="hash")
        stock = Stock(symbol="THYAO", company_name="Turk Hava", is_active=True)
        db_session.add_all([user, stock])
        await db_session.commit()

        wl = Watchlist(user_id=user.id, stock_id=stock.id, notifications_enabled=True)
        db_session.add(wl)
        await db_session.commit()

        result = await toggle_notifications(db_session, wl.id, user.id, enabled=False)

        assert result is not None
        assert result.notifications_enabled is False

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self, db_session: AsyncSession):
        """Should return None when item doesn't exist."""
        user = User(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        await db_session.commit()

        result = await toggle_notifications(db_session, 999, user.id, enabled=True)

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_not_owned(self, db_session: AsyncSession):
        """Should return None when item belongs to another user."""
        user1 = User(username="user1", email="user1@example.com", password_hash="hash")
        user2 = User(username="user2", email="user2@example.com", password_hash="hash")
        stock = Stock(symbol="THYAO", company_name="Turk Hava", is_active=True)
        db_session.add_all([user1, user2, stock])
        await db_session.commit()

        wl = Watchlist(user_id=user2.id, stock_id=stock.id, notifications_enabled=True)
        db_session.add(wl)
        await db_session.commit()

        result = await toggle_notifications(db_session, wl.id, user1.id, enabled=False)

        assert result is None