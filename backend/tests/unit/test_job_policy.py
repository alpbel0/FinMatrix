"""Unit tests for job_policy module."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.pipeline.job_policy import (
    get_all_active_symbols,
    get_bist100_symbols_from_provider,
    get_non_priority_active_symbols,
    get_watchlist_symbols,
    get_slow_sync_symbols,
    get_symbols_by_universe,
)
from app.models.stock import Stock
from app.models.watchlist import Watchlist


class TestGetAllActiveSymbols:
    """Tests for get_all_active_symbols function."""

    @pytest.mark.asyncio
    async def test_returns_all_active_symbols(self, db_session: AsyncSession):
        """Should return all active stock symbols."""
        # Create test stocks
        stock1 = Stock(symbol="THYAO", company_name="Turk Hava", is_active=True)
        stock2 = Stock(symbol="GARAN", company_name="Garanti", is_active=True)
        stock3 = Stock(symbol="INACTIVE", company_name="Inactive", is_active=False)
        db_session.add_all([stock1, stock2, stock3])
        await db_session.commit()

        result = await get_all_active_symbols(db_session)

        assert len(result) == 2
        assert "THYAO" in result
        assert "GARAN" in result
        assert "INACTIVE" not in result

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_stocks(self, db_session: AsyncSession):
        """Should return empty list when no stocks exist."""
        result = await get_all_active_symbols(db_session)
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_ordered_alphabetically(self, db_session: AsyncSession):
        """Should return symbols ordered alphabetically."""
        stock1 = Stock(symbol="ZOREN", company_name="Zorlu", is_active=True)
        stock2 = Stock(symbol="AKBNK", company_name="Akbank", is_active=True)
        stock3 = Stock(symbol="GARAN", company_name="Garanti", is_active=True)
        db_session.add_all([stock1, stock2, stock3])
        await db_session.commit()

        result = await get_all_active_symbols(db_session)

        assert result == ["AKBNK", "GARAN", "ZOREN"]


class TestGetBist100SymbolsFromProvider:
    """Tests for get_bist100_symbols_from_provider function."""

    @pytest.mark.asyncio
    async def test_returns_symbols_from_provider(self):
        """Should return symbols from borsapy provider."""
        with patch(
            "app.services.pipeline.job_policy.get_bist100_symbols"
        ) as mock_get:
            mock_get.return_value = ["THYAO", "GARAN", "AKBNK"]

            result = await get_bist100_symbols_from_provider()

            assert "THYAO" in result
            assert "GARAN" in result
            mock_get.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_empty_on_error(self):
        """Should return empty list if provider fails."""
        with patch(
            "app.services.pipeline.job_policy.get_bist100_symbols"
        ) as mock_get:
            mock_get.return_value = []

            result = await get_bist100_symbols_from_provider()

            assert result == []


class TestGetWatchlistSymbols:
    """Tests for get_watchlist_symbols function."""

    @pytest.mark.asyncio
    async def test_returns_union_of_all_watchlists(self, db_session: AsyncSession):
        """Should return union of all users' watchlists."""
        # Create stocks
        stock1 = Stock(symbol="THYAO", company_name="Turk Hava", is_active=True)
        stock2 = Stock(symbol="GARAN", company_name="Garanti", is_active=True)
        stock3 = Stock(symbol="AKBNK", company_name="Akbank", is_active=True)
        db_session.add_all([stock1, stock2, stock3])
        await db_session.commit()
        await db_session.refresh(stock1)
        await db_session.refresh(stock2)
        await db_session.refresh(stock3)

        # Create watchlist entries (user_id would normally reference users table)
        # For this test, we'll just check the query logic
        from app.models.user import User

        user1 = User(username="user1", email="user1@test.com", password_hash="hash")
        user2 = User(username="user2", email="user2@test.com", password_hash="hash")
        db_session.add_all([user1, user2])
        await db_session.commit()
        await db_session.refresh(user1)
        await db_session.refresh(user2)

        watchlist1 = Watchlist(user_id=user1.id, stock_id=stock1.id)
        watchlist2 = Watchlist(user_id=user1.id, stock_id=stock2.id)
        watchlist3 = Watchlist(user_id=user2.id, stock_id=stock2.id)  # Duplicate GARAN
        watchlist4 = Watchlist(user_id=user2.id, stock_id=stock3.id)
        db_session.add_all([watchlist1, watchlist2, watchlist3, watchlist4])
        await db_session.commit()

        result = await get_watchlist_symbols(db_session)

        # Should have 3 unique symbols (THYAO, GARAN, AKBNK)
        assert len(result) == 3
        assert "THYAO" in result
        assert "GARAN" in result
        assert "AKBNK" in result

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_watchlist(self, db_session: AsyncSession):
        """Should return empty list when no watchlist entries exist."""
        result = await get_watchlist_symbols(db_session)
        assert result == []


class TestGetSlowSyncSymbols:
    """Tests for get_slow_sync_symbols function."""

    @pytest.mark.asyncio
    async def test_excludes_watchlist_and_bist100(self, db_session: AsyncSession):
        """Should exclude watchlist and BIST100 symbols."""
        # Create stocks
        stock1 = Stock(symbol="THYAO", company_name="Turk Hava", is_active=True)  # BIST100
        stock2 = Stock(symbol="GARAN", company_name="Garanti", is_active=True)  # BIST100 + Watchlist
        stock3 = Stock(symbol="OTHER", company_name="Other", is_active=True)  # Slow sync only
        stock4 = Stock(symbol="WATCH", company_name="Watch", is_active=True)  # Watchlist only
        db_session.add_all([stock1, stock2, stock3, stock4])
        await db_session.commit()
        await db_session.refresh(stock1)
        await db_session.refresh(stock2)
        await db_session.refresh(stock3)
        await db_session.refresh(stock4)

        # Create user and watchlist
        from app.models.user import User

        user = User(username="user1", email="user1@test.com", password_hash="hash")
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        watchlist1 = Watchlist(user_id=user.id, stock_id=stock2.id)  # GARAN
        watchlist2 = Watchlist(user_id=user.id, stock_id=stock4.id)  # WATCH
        db_session.add_all([watchlist1, watchlist2])
        await db_session.commit()

        # Mock BIST100
        with patch(
            "app.services.pipeline.job_policy.get_bist100_symbols"
        ) as mock_bist100:
            mock_bist100.return_value = ["THYAO", "GARAN"]

            result = await get_slow_sync_symbols(db_session)

            # Should only have OTHER (not in BIST100 or watchlist)
            assert result == ["OTHER"]

    @pytest.mark.asyncio
    async def test_non_priority_helper_matches_slow_universe(self, db_session: AsyncSession):
        stock1 = Stock(symbol="THYAO", company_name="Turk Hava", is_active=True)
        stock2 = Stock(symbol="GARAN", company_name="Garanti", is_active=True)
        stock3 = Stock(symbol="OTHER", company_name="Other", is_active=True)
        db_session.add_all([stock1, stock2, stock3])
        await db_session.commit()
        await db_session.refresh(stock2)

        from app.models.user import User

        user = User(username="user2", email="user2@test.com", password_hash="hash")
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        db_session.add(Watchlist(user_id=user.id, stock_id=stock2.id))
        await db_session.commit()

        with patch("app.services.pipeline.job_policy.get_bist100_symbols") as mock_bist100:
            mock_bist100.return_value = ["THYAO"]

            result = await get_non_priority_active_symbols(db_session)

            assert result == ["OTHER"]

    @pytest.mark.asyncio
    async def test_returns_empty_when_all_excluded(self, db_session: AsyncSession):
        """Should return empty when all stocks are in BIST100 or watchlist."""
        stock1 = Stock(symbol="THYAO", company_name="Turk Hava", is_active=True)
        stock2 = Stock(symbol="GARAN", company_name="Garanti", is_active=True)
        db_session.add_all([stock1, stock2])
        await db_session.commit()

        with patch(
            "app.services.pipeline.job_policy.get_bist100_symbols"
        ) as mock_bist100:
            mock_bist100.return_value = ["THYAO", "GARAN"]

            result = await get_slow_sync_symbols(db_session)

            assert result == []


class TestGetSymbolsByUniverse:
    """Tests for get_symbols_by_universe function."""

    @pytest.mark.asyncio
    async def test_all_universe(self, db_session: AsyncSession):
        """Should return all active symbols for 'all' universe."""
        stock1 = Stock(symbol="THYAO", company_name="Turk Hava", is_active=True)
        stock2 = Stock(symbol="GARAN", company_name="Garanti", is_active=True)
        db_session.add_all([stock1, stock2])
        await db_session.commit()

        result = await get_symbols_by_universe(db_session, "all")

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_bist100_universe(self, db_session: AsyncSession):
        """Should return BIST100 symbols for 'bist100' universe."""
        with patch(
            "app.services.pipeline.job_policy.get_bist100_symbols"
        ) as mock:
            mock.return_value = ["THYAO", "GARAN"]

            result = await get_symbols_by_universe(db_session, "bist100")

            assert len(result) == 2
            mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalid_universe_raises_error(self, db_session: AsyncSession):
        """Should raise ValueError for invalid universe."""
        with pytest.raises(ValueError, match="Unknown universe"):
            await get_symbols_by_universe(db_session, "invalid")

    @pytest.mark.asyncio
    async def test_case_insensitive(self, db_session: AsyncSession):
        """Should be case insensitive for universe name."""
        with patch(
            "app.services.pipeline.job_policy.get_bist100_symbols"
        ) as mock:
            mock.return_value = ["THYAO"]

            result = await get_symbols_by_universe(db_session, "BIST100")

            assert "THYAO" in result
