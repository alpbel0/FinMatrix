"""Integration tests for stocks API endpoints."""

import pytest
from datetime import date

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stock import Stock
from app.models.stock_price import StockPrice
from app.models.stock_snapshot import StockSnapshotRecord


@pytest.fixture
async def auth_header(client: AsyncClient) -> dict:
    """Get auth header with valid token."""
    response = await client.post(
        "/api/auth/register",
        json={"username": "testuser", "email": "test@example.com", "password": "password123"}
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def seeded_stocks(db_session: AsyncSession):
    """Seed test stocks."""
    stocks = [
        Stock(symbol="THYAO", company_name="Turk Hava Yollari", sector="Transportation", is_active=True),
        Stock(symbol="GARAN", company_name="Garanti Bankasi", sector="Finance", is_active=True),
        Stock(symbol="AKBNK", company_name="Akbank", sector="Finance", is_active=True),
        Stock(symbol="INACTIVE", company_name="Inactive Stock", sector="Test", is_active=False),
    ]
    db_session.add_all(stocks)
    await db_session.commit()
    return stocks


@pytest.fixture
async def seeded_prices(db_session: AsyncSession, seeded_stocks):
    """Seed test prices for THYAO."""
    thyao = seeded_stocks[0]
    prices = [
        StockPrice(stock_id=thyao.id, date=date(2024, 1, 1), open=100.0, high=105.0, low=99.0, close=102.0, volume=1000.0),
        StockPrice(stock_id=thyao.id, date=date(2024, 1, 2), open=102.0, high=107.0, low=101.0, close=105.0, volume=1200.0),
        StockPrice(stock_id=thyao.id, date=date(2024, 1, 3), open=105.0, high=110.0, low=104.0, close=108.0, volume=1500.0),
    ]
    db_session.add_all(prices)
    await db_session.commit()
    return prices


class TestListStocks:
    """Test GET /api/stocks."""

    @pytest.mark.asyncio
    async def test_list_stocks_authorized(self, client: AsyncClient, auth_header: dict, seeded_stocks):
        """Authorized request should return stocks list."""
        response = await client.get("/api/stocks", headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        assert "stocks" in data
        assert "total" in data
        assert data["total"] == 3  # Only active stocks

    @pytest.mark.asyncio
    async def test_list_stocks_unauthorized(self, client: AsyncClient):
        """Unauthorized request should return 401."""
        response = await client.get("/api/stocks")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_list_stocks_with_search(self, client: AsyncClient, auth_header: dict, seeded_stocks):
        """Search filter should work."""
        response = await client.get("/api/stocks?search=THY", headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["stocks"][0]["symbol"] == "THYAO"

    @pytest.mark.asyncio
    async def test_list_stocks_search_case_insensitive(self, client: AsyncClient, auth_header: dict, seeded_stocks):
        """Search should be case insensitive."""
        response = await client.get("/api/stocks?search=thyao", headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1

    @pytest.mark.asyncio
    async def test_list_stocks_excludes_inactive(self, client: AsyncClient, auth_header: dict, seeded_stocks):
        """Should exclude inactive stocks."""
        response = await client.get("/api/stocks", headers=auth_header)
        data = response.json()
        symbols = [s["symbol"] for s in data["stocks"]]
        assert "INACTIVE" not in symbols

    @pytest.mark.asyncio
    async def test_list_stocks_empty(self, client: AsyncClient, auth_header: dict):
        """Empty result should return empty list."""
        response = await client.get("/api/stocks?search=NOTEXIST", headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["stocks"] == []


class TestGetStockDetail:
    """Test GET /api/stocks/{symbol}."""

    @pytest.mark.asyncio
    async def test_get_stock_found(self, client: AsyncClient, auth_header: dict, seeded_stocks):
        """Should return stock detail for valid symbol."""
        response = await client.get("/api/stocks/THYAO", headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "THYAO"
        assert data["company_name"] == "Turk Hava Yollari"
        assert data["sector"] == "Transportation"
        assert data["exchange"] == "BIST"
        assert data["is_active"] is True

    @pytest.mark.asyncio
    async def test_get_stock_not_found(self, client: AsyncClient, auth_header: dict):
        """Should return 404 for non-existent symbol."""
        response = await client.get("/api/stocks/NOTEXIST", headers=auth_header)
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_stock_unauthorized(self, client: AsyncClient):
        """Should return 401 without auth."""
        response = await client.get("/api/stocks/THYAO")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_get_stock_symbol_case_insensitive(self, client: AsyncClient, auth_header: dict, seeded_stocks):
        """Should work with lowercase symbol."""
        response = await client.get("/api/stocks/thyao", headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "THYAO"


class TestGetPriceHistory:
    """Test GET /api/stocks/{symbol}/prices."""

    @pytest.mark.asyncio
    async def test_get_prices_success(self, client: AsyncClient, auth_header: dict, seeded_prices):
        """Should return price history for stock."""
        response = await client.get("/api/stocks/THYAO/prices", headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "THYAO"
        assert data["count"] == 3
        assert len(data["prices"]) == 3
        assert data["prices"][0]["date"] == "2024-01-01"
        assert data["prices"][0]["close"] == 102.0

    @pytest.mark.asyncio
    async def test_get_prices_with_date_filter(self, client: AsyncClient, auth_header: dict, seeded_prices):
        """Should filter by date range."""
        response = await client.get(
            "/api/stocks/THYAO/prices?start_date=2024-01-02&end_date=2024-01-02",
            headers=auth_header
        )
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["prices"][0]["date"] == "2024-01-02"

    @pytest.mark.asyncio
    async def test_get_prices_stock_not_found(self, client: AsyncClient, auth_header: dict):
        """Should return 404 for non-existent stock."""
        response = await client.get("/api/stocks/NOTEXIST/prices", headers=auth_header)
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_prices_unauthorized(self, client: AsyncClient):
        """Should return 401 without auth."""
        response = await client.get("/api/stocks/THYAO/prices")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_get_prices_empty(self, client: AsyncClient, auth_header: dict, seeded_stocks):
        """Should return empty list for stock with no prices."""
        response = await client.get("/api/stocks/GARAN/prices", headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert data["prices"] == []


class TestStockSnapshotsApi:
    @pytest.mark.asyncio
    async def test_get_latest_snapshot_returns_latest_data(self, client: AsyncClient, auth_header: dict, seeded_stocks, db_session: AsyncSession):
        thyao = seeded_stocks[0]
        db_session.add(
            StockSnapshotRecord(
                stock_id=thyao.id,
                snapshot_date=date(2026, 4, 20),
                pe_ratio=6.2,
                roe=0.24,
                roa=0.12,
                current_ratio=1.8,
                debt_equity=1.35,
                net_profit_growth=0.18,
                market_cap=500_000_000_000,
                last_price=290.5,
                daily_volume=1_200_000,
                source="provider:borsapy+calculated",
                field_sources={"pe_ratio": "provider:borsapy", "roe": "calculated"},
                missing_fields_count=0,
                completeness_score=1.0,
                is_partial=False,
            )
        )
        await db_session.commit()

        response = await client.get("/api/stocks/THYAO/snapshot/latest", headers=auth_header)

        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "THYAO"
        assert data["snapshot_date"] == "2026-04-20"
        assert data["pe_ratio"] == 6.2
        assert data["roe"] == 0.24
        assert data["roa"] == 0.12
        assert data["current_ratio"] == 1.8
        assert data["debt_equity"] == 1.35
        assert data["net_profit_growth"] == 0.18
        assert data["source"] == "provider:borsapy+calculated"
        assert data["field_sources"]["roe"] == "calculated"

    @pytest.mark.asyncio
    async def test_get_latest_snapshot_returns_empty_payload_when_missing(self, client: AsyncClient, auth_header: dict, seeded_stocks):
        response = await client.get("/api/stocks/THYAO/snapshot/latest", headers=auth_header)

        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "THYAO"
        assert data["snapshot_date"] is None
        assert data["is_stale"] is True
        assert data["stale_reason"] == "no_snapshot"

    @pytest.mark.asyncio
    async def test_get_prices_ordered_by_date(self, client: AsyncClient, auth_header: dict, seeded_prices):
        """Should return prices ordered by date ascending."""
        response = await client.get("/api/stocks/THYAO/prices", headers=auth_header)
        data = response.json()
        dates = [p["date"] for p in data["prices"]]
        assert dates == ["2024-01-01", "2024-01-02", "2024-01-03"]
