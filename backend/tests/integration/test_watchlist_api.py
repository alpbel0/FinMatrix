"""Integration tests for Watchlist API endpoints."""

import pytest
from httpx import AsyncClient

from app.models.stock import Stock
from app.models.user import User
from app.models.watchlist import Watchlist
from tests.factories import create_user_in_db, get_auth_headers


class TestListWatchlist:
    """Tests for GET /api/watchlist endpoint."""

    @pytest.mark.asyncio
    async def test_returns_empty_list_for_new_user(self, client: AsyncClient, db_session):
        """Should return empty watchlist for user with no items."""
        user = await create_user_in_db(db_session, username="testuser")
        headers = await get_auth_headers(client, user.username)

        response = await client.get("/api/watchlist", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_returns_watchlist_with_price_snapshot(self, client: AsyncClient, db_session):
        """Should return watchlist items with latest price."""
        from datetime import date
        from app.models.stock_price import StockPrice

        user = await create_user_in_db(db_session, username="testuser")
        headers = await get_auth_headers(client, user.username)

        # Create stock and price
        stock = Stock(symbol="THYAO", company_name="Turk Hava", sector="Transportation", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        # Create prices for change calculation
        price1 = StockPrice(stock_id=stock.id, date=date(2026, 1, 1), close=100.0)
        price2 = StockPrice(stock_id=stock.id, date=date(2026, 1, 2), close=110.0)
        db_session.add_all([price1, price2])
        await db_session.commit()

        # Add to watchlist directly
        wl = Watchlist(user_id=user.id, stock_id=stock.id)
        db_session.add(wl)
        await db_session.commit()

        response = await client.get("/api/watchlist", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        item = data["items"][0]
        assert item["symbol"] == "THYAO"
        assert item["latest_price"] == 110.0
        assert item["price_change"] == 10.0
        assert item["price_change_percent"] == 10.0

    @pytest.mark.asyncio
    async def test_requires_authentication(self, client: AsyncClient):
        """Should return 401 without auth token."""
        response = await client.get("/api/watchlist")

        assert response.status_code == 401


class TestAddToWatchlist:
    """Tests for POST /api/watchlist endpoint."""

    @pytest.mark.asyncio
    async def test_adds_stock_to_watchlist(self, client: AsyncClient, db_session):
        """Should add stock to user's watchlist."""
        user = await create_user_in_db(db_session, username="testuser")
        headers = await get_auth_headers(client, user.username)

        stock = Stock(symbol="THYAO", company_name="Turk Hava", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        response = await client.post(
            "/api/watchlist",
            headers=headers,
            json={"symbol": "THYAO", "notifications_enabled": True},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["symbol"] == "THYAO"
        assert data["notifications_enabled"] is True

    @pytest.mark.asyncio
    async def test_returns_404_for_nonexistent_stock(self, client: AsyncClient, db_session):
        """Should return 404 when stock doesn't exist."""
        user = await create_user_in_db(db_session, username="testuser")
        headers = await get_auth_headers(client, user.username)

        response = await client.post(
            "/api/watchlist",
            headers=headers,
            json={"symbol": "NONEXISTENT"},
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_returns_400_for_duplicate(self, client: AsyncClient, db_session):
        """Should return 400 when stock already in watchlist."""
        user = await create_user_in_db(db_session, username="testuser")
        headers = await get_auth_headers(client, user.username)

        stock = Stock(symbol="THYAO", company_name="Turk Hava", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        # Add first time
        await client.post(
            "/api/watchlist",
            headers=headers,
            json={"symbol": "THYAO"},
        )

        # Try to add again
        response = await client.post(
            "/api/watchlist",
            headers=headers,
            json={"symbol": "THYAO"},
        )

        assert response.status_code == 400
        assert "already" in response.json()["detail"].lower()


class TestRemoveFromWatchlist:
    """Tests for DELETE /api/watchlist/{id} endpoint."""

    @pytest.mark.asyncio
    async def test_removes_item(self, client: AsyncClient, db_session):
        """Should remove item from watchlist."""
        user = await create_user_in_db(db_session, username="testuser")
        headers = await get_auth_headers(client, user.username)

        stock = Stock(symbol="THYAO", company_name="Turk Hava", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        wl = Watchlist(user_id=user.id, stock_id=stock.id)
        db_session.add(wl)
        await db_session.commit()

        response = await client.delete(f"/api/watchlist/{wl.id}", headers=headers)

        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_returns_404_for_nonexistent_item(self, client: AsyncClient, db_session):
        """Should return 404 when item doesn't exist."""
        user = await create_user_in_db(db_session, username="testuser")
        headers = await get_auth_headers(client, user.username)

        response = await client.delete("/api/watchlist/999", headers=headers)

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_404_for_other_users_item(self, client: AsyncClient, db_session):
        """Should not allow deleting another user's item."""
        user1 = await create_user_in_db(db_session, username="user1")
        user2 = await create_user_in_db(db_session, username="user2")
        headers1 = await get_auth_headers(client, user1.username)

        stock = Stock(symbol="THYAO", company_name="Turk Hava", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        # Create item for user2
        wl = Watchlist(user_id=user2.id, stock_id=stock.id)
        db_session.add(wl)
        await db_session.commit()

        # Try to delete as user1
        response = await client.delete(f"/api/watchlist/{wl.id}", headers=headers1)

        assert response.status_code == 404


class TestToggleNotifications:
    """Tests for PATCH /api/watchlist/{id}/notifications endpoint."""

    @pytest.mark.asyncio
    async def test_toggles_notifications(self, client: AsyncClient, db_session):
        """Should update notifications setting."""
        user = await create_user_in_db(db_session, username="testuser")
        headers = await get_auth_headers(client, user.username)

        stock = Stock(symbol="THYAO", company_name="Turk Hava", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        wl = Watchlist(user_id=user.id, stock_id=stock.id, notifications_enabled=True)
        db_session.add(wl)
        await db_session.commit()

        response = await client.patch(
            f"/api/watchlist/{wl.id}/notifications",
            headers=headers,
            json={"notifications_enabled": False},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["notifications_enabled"] is False

    @pytest.mark.asyncio
    async def test_returns_404_for_nonexistent_item(self, client: AsyncClient, db_session):
        """Should return 404 when item doesn't exist."""
        user = await create_user_in_db(db_session, username="testuser")
        headers = await get_auth_headers(client, user.username)

        response = await client.patch(
            "/api/watchlist/999/notifications",
            headers=headers,
            json={"notifications_enabled": False},
        )

        assert response.status_code == 404