"""Integration tests for News API endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.news import News, UserNews
from app.models.stock import Stock
from app.models.user import User
from tests.factories import create_user_in_db, get_auth_headers


class TestListNews:
    """Tests for GET /api/news endpoint."""

    @pytest.mark.asyncio
    async def test_returns_news_feed(self, client: AsyncClient, db_session):
        """Should return news feed with items."""
        user = await create_user_in_db(db_session, username="testuser")
        headers = await get_auth_headers(client, user.username)

        stock = Stock(symbol="THYAO", company_name="Turk Hava", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        news = News(
            stock_id=stock.id,
            title="Test News Item",
            category="financial",
            source_type="kap",
            source_id=1,
        )
        db_session.add(news)
        await db_session.commit()

        response = await client.get("/api/news", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["title"] == "Test News Item"

    @pytest.mark.asyncio
    async def test_includes_user_specific_is_read(self, client: AsyncClient, db_session):
        """Should include user-specific is_read status."""
        user = await create_user_in_db(db_session, username="testuser")
        headers = await get_auth_headers(client, user.username)

        stock = Stock(symbol="THYAO", company_name="Turk Hava", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        news = News(
            stock_id=stock.id,
            title="Test News",
            category="kap",
            source_type="kap",
            source_id=1,
        )
        db_session.add(news)
        await db_session.commit()

        # Mark as read for this user
        user_news = UserNews(user_id=user.id, news_id=news.id, is_read=True)
        db_session.add(user_news)
        await db_session.commit()

        response = await client.get("/api/news", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["items"][0]["is_read"] is True

    @pytest.mark.asyncio
    async def test_filters_by_category(self, client: AsyncClient, db_session):
        """Should filter news by category."""
        user = await create_user_in_db(db_session, username="testuser")
        headers = await get_auth_headers(client, user.username)

        stock = Stock(symbol="THYAO", company_name="Turk Hava", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        news1 = News(
            stock_id=stock.id,
            title="Financial News",
            category="financial",
            source_type="kap",
            source_id=1,
        )
        news2 = News(
            stock_id=stock.id,
            title="Activity News",
            category="activity",
            source_type="kap",
            source_id=2,
        )
        db_session.add_all([news1, news2])
        await db_session.commit()

        response = await client.get("/api/news?category=financial", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["category"] == "financial"

    @pytest.mark.asyncio
    async def test_returns_unread_count(self, client: AsyncClient, db_session):
        """Should return correct unread count."""
        user = await create_user_in_db(db_session, username="testuser")
        headers = await get_auth_headers(client, user.username)

        stock = Stock(symbol="THYAO", company_name="Turk Hava", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        # Create 3 news items
        for i in range(3):
            news = News(
                stock_id=stock.id,
                title=f"News {i}",
                category="kap",
                source_type="kap",
                source_id=i + 1,
            )
            db_session.add(news)
        await db_session.commit()

        # Mark 1 as read
        result = await db_session.execute(select(News).limit(1))
        first_news = result.scalar_one()
        user_news = UserNews(user_id=user.id, news_id=first_news.id, is_read=True)
        db_session.add(user_news)
        await db_session.commit()

        response = await client.get("/api/news", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["unread_count"] == 2

    @pytest.mark.asyncio
    async def test_requires_authentication(self, client: AsyncClient):
        """Should return 401 without auth token."""
        response = await client.get("/api/news")

        assert response.status_code == 401


class TestGetNewsItem:
    """Tests for GET /api/news/{id} endpoint."""

    @pytest.mark.asyncio
    async def test_returns_news_detail(self, client: AsyncClient, db_session):
        """Should return single news item detail."""
        user = await create_user_in_db(db_session, username="testuser")
        headers = await get_auth_headers(client, user.username)

        stock = Stock(symbol="THYAO", company_name="Turk Hava", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        news = News(
            stock_id=stock.id,
            title="Test News Detail",
            category="financial",
            excerpt="This is an excerpt",
            source_type="kap",
            source_id=1,
        )
        db_session.add(news)
        await db_session.commit()

        response = await client.get(f"/api/news/{news.id}", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Test News Detail"
        assert data["excerpt"] == "This is an excerpt"

    @pytest.mark.asyncio
    async def test_returns_404_for_nonexistent(self, client: AsyncClient, db_session):
        """Should return 404 for nonexistent news ID."""
        user = await create_user_in_db(db_session, username="testuser")
        headers = await get_auth_headers(client, user.username)

        response = await client.get("/api/news/999", headers=headers)

        assert response.status_code == 404


class TestMarkNewsRead:
    """Tests for POST /api/news/{id}/read endpoint."""

    @pytest.mark.asyncio
    async def test_marks_news_as_read(self, client: AsyncClient, db_session):
        """Should mark news as read for user."""
        user = await create_user_in_db(db_session, username="testuser")
        headers = await get_auth_headers(client, user.username)

        stock = Stock(symbol="THYAO", company_name="Turk Hava", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        news = News(
            stock_id=stock.id,
            title="Test News",
            category="kap",
            source_type="kap",
            source_id=1,
        )
        db_session.add(news)
        await db_session.commit()

        response = await client.post(
            f"/api/news/{news.id}/read",
            headers=headers,
            json={"is_read": True},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["is_read"] is True

        # Verify in database
        result = await db_session.execute(
            select(UserNews).where(
                UserNews.user_id == user.id,
                UserNews.news_id == news.id,
            )
        )
        user_news = result.scalar_one_or_none()
        assert user_news is not None
        assert user_news.is_read is True

    @pytest.mark.asyncio
    async def test_marks_news_as_unread(self, client: AsyncClient, db_session):
        """Should mark news as unread for user."""
        user = await create_user_in_db(db_session, username="testuser")
        headers = await get_auth_headers(client, user.username)

        stock = Stock(symbol="THYAO", company_name="Turk Hava", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        news = News(
            stock_id=stock.id,
            title="Test News",
            category="kap",
            source_type="kap",
            source_id=1,
        )
        db_session.add(news)
        await db_session.commit()

        # First mark as read
        user_news = UserNews(user_id=user.id, news_id=news.id, is_read=True)
        db_session.add(user_news)
        await db_session.commit()

        # Then mark as unread
        response = await client.post(
            f"/api/news/{news.id}/read",
            headers=headers,
            json={"is_read": False},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["is_read"] is False

    @pytest.mark.asyncio
    async def test_returns_404_for_nonexistent_news(self, client: AsyncClient, db_session):
        """Should return 404 for nonexistent news ID."""
        user = await create_user_in_db(db_session, username="testuser")
        headers = await get_auth_headers(client, user.username)

        response = await client.post(
            "/api/news/999/read",
            headers=headers,
            json={"is_read": True},
        )

        assert response.status_code == 404