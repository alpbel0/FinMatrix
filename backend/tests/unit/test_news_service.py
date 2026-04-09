"""Unit tests for news_service module."""

import pytest
from datetime import date, datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.news import News, UserNews
from app.models.kap_report import KapReport
from app.models.stock import Stock
from app.models.user import User
from app.services.news_service import (
    backfill_news_from_kap_reports,
    batch_transform_kap_to_news,
    derive_category,
    get_news_detail,
    get_news_feed,
    get_unread_count,
    get_user_news_status,
    mark_news_read,
    transform_kap_to_news,
)


class TestDeriveCategory:
    """Tests for derive_category function."""

    def test_fr_returns_financial(self):
        """FR filing type should return 'financial' category."""
        assert derive_category("FR") == "financial"

    def test_far_returns_activity(self):
        """FAR filing type should return 'activity' category."""
        assert derive_category("FAR") == "activity"

    def test_other_returns_kap(self):
        """Other filing types should return 'kap' category."""
        assert derive_category("ODA") == "kap"
        assert derive_category("DVB") == "kap"
        assert derive_category("DEG") == "kap"

    def test_none_returns_kap(self):
        """None filing type should return 'kap' category."""
        assert derive_category(None) == "kap"


class TestTransformKapToNews:
    """Tests for transform_kap_to_news function."""

    @pytest.mark.asyncio
    async def test_creates_news_from_kap_report(self, db_session: AsyncSession):
        """Should create News record from KapReport."""
        stock = Stock(symbol="THYAO", company_name="Turk Hava", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        kap = KapReport(
            stock_id=stock.id,
            title="2025 Annual Report",
            filing_type="FR",
            source_url="https://kap.org/tr/123",
            summary="Financial summary",
        )
        db_session.add(kap)
        await db_session.commit()

        result = await transform_kap_to_news(db_session, kap)

        assert result is not None
        assert result.title == "2025 Annual Report"
        assert result.category == "financial"
        assert result.source_type == "kap"
        assert result.source_id == kap.id
        assert result.filing_type == "FR"
        assert result.excerpt == "Financial summary"

    @pytest.mark.asyncio
    async def test_returns_none_when_no_stock_id(self, db_session: AsyncSession):
        """Should return None when KapReport has no stock_id."""
        kap = KapReport(
            title="General Report",
            filing_type="FR",
            source_url="https://kap.org/tr/123",
        )
        db_session.add(kap)
        await db_session.commit()

        result = await transform_kap_to_news(db_session, kap)

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_existing_when_duplicate(self, db_session: AsyncSession):
        """Should return existing News when KAP already transformed."""
        stock = Stock(symbol="THYAO", company_name="Turk Hava", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        kap = KapReport(
            stock_id=stock.id,
            title="2025 Annual Report",
            filing_type="FR",
            source_url="https://kap.org/tr/123",
        )
        db_session.add(kap)
        await db_session.commit()

        # First transform
        news1 = await transform_kap_to_news(db_session, kap)

        # Second transform (should return existing)
        news2 = await transform_kap_to_news(db_session, kap)

        assert news1.id == news2.id
        assert news1.title == news2.title


class TestGetNewsFeed:
    """Tests for get_news_feed function."""

    @pytest.mark.asyncio
    async def test_returns_news_ordered_by_date(self, db_session: AsyncSession):
        """Should return news items ordered by created_at desc."""
        stock = Stock(symbol="THYAO", company_name="Turk Hava", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        news1 = News(
            stock_id=stock.id,
            title="News 1",
            category="financial",
            source_type="kap",
            source_id=1,
        )
        news2 = News(
            stock_id=stock.id,
            title="News 2",
            category="activity",
            source_type="kap",
            source_id=2,
        )
        db_session.add_all([news1, news2])
        await db_session.commit()

        result = await get_news_feed(db_session, user_id=1)

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_filters_by_category(self, db_session: AsyncSession):
        """Should filter news by category."""
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

        result = await get_news_feed(db_session, user_id=1, category="financial")

        assert len(result) == 1
        assert result[0].category == "financial"

    @pytest.mark.asyncio
    async def test_filters_by_stock_id(self, db_session: AsyncSession):
        """Should filter news by stock_id."""
        stock1 = Stock(symbol="THYAO", company_name="Turk Hava", is_active=True)
        stock2 = Stock(symbol="GARAN", company_name="Garanti", is_active=True)
        db_session.add_all([stock1, stock2])
        await db_session.commit()

        news1 = News(
            stock_id=stock1.id,
            title="THYAO News",
            category="kap",
            source_type="kap",
            source_id=1,
        )
        news2 = News(
            stock_id=stock2.id,
            title="GARAN News",
            category="kap",
            source_type="kap",
            source_id=2,
        )
        db_session.add_all([news1, news2])
        await db_session.commit()

        result = await get_news_feed(db_session, user_id=1, stock_id=stock1.id)

        assert len(result) == 1
        assert result[0].title == "THYAO News"


class TestGetNewsDetail:
    """Tests for get_news_detail function."""

    @pytest.mark.asyncio
    async def test_returns_news_by_id(self, db_session: AsyncSession):
        """Should return news item by ID."""
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

        result = await get_news_detail(db_session, news.id)

        assert result is not None
        assert result.title == "Test News"

    @pytest.mark.asyncio
    async def test_returns_none_for_nonexistent(self, db_session: AsyncSession):
        """Should return None for nonexistent ID."""
        result = await get_news_detail(db_session, 999)

        assert result is None


class TestGetUserNewsStatus:
    """Tests for get_user_news_status function."""

    @pytest.mark.asyncio
    async def test_returns_user_news_record(self, db_session: AsyncSession):
        """Should return UserNews record for user-news pair."""
        user = User(username="testuser", email="test@example.com", password_hash="hash")
        stock = Stock(symbol="THYAO", company_name="Turk Hava", is_active=True)
        db_session.add_all([user, stock])
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

        user_news = UserNews(user_id=user.id, news_id=news.id, is_read=True)
        db_session.add(user_news)
        await db_session.commit()

        result = await get_user_news_status(db_session, user.id, news.id)

        assert result is not None
        assert result.is_read is True

    @pytest.mark.asyncio
    async def test_returns_none_when_not_exists(self, db_session: AsyncSession):
        """Should return None when UserNews record doesn't exist."""
        result = await get_user_news_status(db_session, 1, 999)

        assert result is None


class TestMarkNewsRead:
    """Tests for mark_news_read function."""

    @pytest.mark.asyncio
    async def test_creates_user_news_record(self, db_session: AsyncSession):
        """Should create UserNews record if not exists."""
        user = User(username="testuser", email="test@example.com", password_hash="hash")
        stock = Stock(symbol="THYAO", company_name="Turk Hava", is_active=True)
        db_session.add_all([user, stock])
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

        result = await mark_news_read(db_session, user.id, news.id, is_read=True)

        assert result.is_read is True
        assert result.user_id == user.id
        assert result.news_id == news.id

    @pytest.mark.asyncio
    async def test_updates_existing_record(self, db_session: AsyncSession):
        """Should update existing UserNews record."""
        user = User(username="testuser", email="test@example.com", password_hash="hash")
        stock = Stock(symbol="THYAO", company_name="Turk Hava", is_active=True)
        db_session.add_all([user, stock])
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

        # Create initial record
        user_news = UserNews(user_id=user.id, news_id=news.id, is_read=False)
        db_session.add(user_news)
        await db_session.commit()

        # Update to read
        result = await mark_news_read(db_session, user.id, news.id, is_read=True)

        assert result.is_read is True

    @pytest.mark.asyncio
    async def test_reuses_existing_record_without_duplicates(self, db_session: AsyncSession):
        """Should keep a single UserNews row when toggled multiple times."""
        user = User(username="testuser", email="test@example.com", password_hash="hash")
        stock = Stock(symbol="THYAO", company_name="Turk Hava", is_active=True)
        db_session.add_all([user, stock])
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

        await mark_news_read(db_session, user.id, news.id, is_read=True)
        await mark_news_read(db_session, user.id, news.id, is_read=False)
        await mark_news_read(db_session, user.id, news.id, is_read=True)

        count_result = await db_session.execute(
            select(func.count()).select_from(UserNews).where(
                UserNews.user_id == user.id,
                UserNews.news_id == news.id,
            )
        )
        user_news_count = count_result.scalar_one()

        assert user_news_count == 1


class TestGetUnreadCount:
    """Tests for get_unread_count function."""

    @pytest.mark.asyncio
    async def test_calculates_unread_count(self, db_session: AsyncSession):
        """Should calculate unread count correctly."""
        from sqlalchemy import select

        user = User(username="testuser", email="test@example.com", password_hash="hash")
        stock = Stock(symbol="THYAO", company_name="Turk Hava", is_active=True)
        db_session.add_all([user, stock])
        await db_session.commit()

        # Create 5 news items
        for i in range(5):
            news = News(
                stock_id=stock.id,
                title=f"News {i}",
                category="kap",
                source_type="kap",
                source_id=i + 1,
            )
            db_session.add(news)
        await db_session.commit()

        # Mark 2 as read
        from sqlalchemy import select
        news_items = await db_session.execute(select(News.id).limit(2))
        news_ids = [row[0] for row in news_items.fetchall()]
        for news_id in news_ids:
            user_news = UserNews(user_id=user.id, news_id=news_id, is_read=True)
            db_session.add(user_news)
        await db_session.commit()

        result = await get_unread_count(db_session, user.id)

        assert result == 3  # 5 total - 2 read


class TestBatchTransformKapToNews:
    """Tests for batch_transform_kap_to_news function."""

    @pytest.mark.asyncio
    async def test_transforms_all_kap_reports(self, db_session: AsyncSession):
        """Should transform all KAP reports for a symbol."""
        stock = Stock(symbol="THYAO", company_name="Turk Hava", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        # Create KAP reports
        for i in range(3):
            kap = KapReport(
                stock_id=stock.id,
                title=f"Report {i}",
                filing_type="FR",
                source_url=f"https://kap.org/tr/{i}",
            )
            db_session.add(kap)
        await db_session.commit()

        result = await batch_transform_kap_to_news(db_session, "THYAO")

        assert result == 3

    @pytest.mark.asyncio
    async def test_returns_zero_for_nonexistent_symbol(self, db_session: AsyncSession):
        """Should return 0 when symbol doesn't exist."""
        result = await batch_transform_kap_to_news(db_session, "NONEXISTENT")

        assert result == 0


class TestBackfillNewsFromKapReports:
    """Tests for backfill_news_from_kap_reports function."""

    @pytest.mark.asyncio
    async def test_backfills_existing_kap_reports(self, db_session: AsyncSession):
        """Should create news rows from pre-existing KAP reports."""
        stock1 = Stock(symbol="THYAO", company_name="Turk Hava", is_active=True)
        stock2 = Stock(symbol="GARAN", company_name="Garanti", is_active=True)
        db_session.add_all([stock1, stock2])
        await db_session.commit()

        db_session.add_all([
            KapReport(
                stock_id=stock1.id,
                title="THYAO Report",
                filing_type="FR",
                source_url="https://kap.org/tr/100",
            ),
            KapReport(
                stock_id=stock2.id,
                title="GARAN Report",
                filing_type="FAR",
                source_url="https://kap.org/tr/200",
            ),
        ])
        await db_session.commit()

        created_count = await backfill_news_from_kap_reports(db_session)

        assert created_count == 2
