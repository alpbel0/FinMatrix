"""
Integration tests for database constraints.

Tests verify:
- Unique constraints
- Composite primary keys
- Foreign key constraints
- NOT NULL constraints
"""

import pytest
from datetime import datetime, date, timezone
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.models import (
    User,
    TelegramSettings,
    Stock,
    Watchlist,
    StockPrice,
    BalanceSheet,
    IncomeStatement,
    CashFlow,
    KAPReport,
    News,
    UserNews,
    ChatSession,
    ChatMessage,
    DocumentChunk,
)
from app.models.enums import PeriodType, MessageRole, MessageType, NewsSource
from tests.factories import (
    UserFactory,
    TelegramSettingsFactory,
    StockFactory,
    WatchlistFactory,
    StockPriceFactory,
    BalanceSheetFactory,
    IncomeStatementFactory,
    CashFlowFactory,
    KAPReportFactory,
    NewsFactory,
    UserNewsFactory,
    ChatSessionFactory,
    ChatMessageFactory,
    DocumentChunkFactory,
    create_user_async,
    create_stock_async,
    create_chat_session_async,
    create_kap_report_async,
)


# --- Unique Constraint Tests ---

class TestUniqueConstraints:
    """Tests for unique constraints."""

    @pytest.mark.asyncio
    async def test_user_email_unique(self, test_session: AsyncSession):
        """User email should be unique."""
        await create_user_async(test_session, email="unique@test.com")

        duplicate = UserFactory.build(email="unique@test.com")
        test_session.add(duplicate)

        with pytest.raises(IntegrityError) as exc_info:
            await test_session.flush()

        assert "unique" in str(exc_info.value).lower() or "duplicate" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_user_username_unique(self, test_session: AsyncSession):
        """User username should be unique."""
        await create_user_async(test_session, username="uniqueuser")

        duplicate = UserFactory.build(username="uniqueuser")
        test_session.add(duplicate)

        with pytest.raises(IntegrityError) as exc_info:
            await test_session.flush()

        assert "unique" in str(exc_info.value).lower() or "duplicate" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_stock_symbol_unique(self, test_session: AsyncSession):
        """Stock symbol should be unique."""
        await create_stock_async(test_session, symbol="UNIQUE")

        duplicate = StockFactory.build(symbol="UNIQUE")
        test_session.add(duplicate)

        with pytest.raises(IntegrityError) as exc_info:
            await test_session.flush()

        assert "unique" in str(exc_info.value).lower() or "duplicate" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_stock_yfinance_symbol_unique(self, test_session: AsyncSession):
        """Stock yfinance_symbol should be unique."""
        await create_stock_async(test_session, symbol="TEST1", yfinance_symbol="UNIQUE.IS")

        duplicate = StockFactory.build(symbol="TEST2", yfinance_symbol="UNIQUE.IS")
        test_session.add(duplicate)

        with pytest.raises(IntegrityError) as exc_info:
            await test_session.flush()

        assert "unique" in str(exc_info.value).lower() or "duplicate" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_kap_report_bildirim_no_unique(self, test_session: AsyncSession):
        """KAPReport bildirim_no should be unique."""
        stock = await create_stock_async(test_session, symbol="KAPUNIQUE")

        await create_kap_report_async(test_session, stock_id=stock.id, bildirim_no="UNIQUE-001")

        duplicate = KAPReportFactory.build(bildirim_no="UNIQUE-001")
        test_session.add(duplicate)

        with pytest.raises(IntegrityError) as exc_info:
            await test_session.flush()

        assert "unique" in str(exc_info.value).lower() or "duplicate" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_balance_sheet_unique_stock_period_date(self, test_session: AsyncSession):
        """BalanceSheet should have unique (stock_id, period, date)."""
        stock = await create_stock_async(test_session, symbol="BSUNIQUE")
        bs_date = date.today()

        bs1 = BalanceSheetFactory.build(
            stock_id=stock.id, period=PeriodType.Q1, date=bs_date
        )
        test_session.add(bs1)
        await test_session.flush()

        bs2 = BalanceSheetFactory.build(
            stock_id=stock.id, period=PeriodType.Q1, date=bs_date
        )
        test_session.add(bs2)

        with pytest.raises(IntegrityError) as exc_info:
            await test_session.flush()

        assert "unique" in str(exc_info.value).lower() or "duplicate" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_income_statement_unique_stock_period_date(self, test_session: AsyncSession):
        """IncomeStatement should have unique (stock_id, period, date)."""
        stock = await create_stock_async(test_session, symbol="ISUNIQUE")
        is_date = date.today()

        is1 = IncomeStatementFactory.build(
            stock_id=stock.id, period=PeriodType.Q1, date=is_date
        )
        test_session.add(is1)
        await test_session.flush()

        is2 = IncomeStatementFactory.build(
            stock_id=stock.id, period=PeriodType.Q1, date=is_date
        )
        test_session.add(is2)

        with pytest.raises(IntegrityError) as exc_info:
            await test_session.flush()

        assert "unique" in str(exc_info.value).lower() or "duplicate" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_cash_flow_unique_stock_period_date(self, test_session: AsyncSession):
        """CashFlow should have unique (stock_id, period, date)."""
        stock = await create_stock_async(test_session, symbol="CFUNIQUE")
        cf_date = date.today()

        cf1 = CashFlowFactory.build(
            stock_id=stock.id, period=PeriodType.Q1, date=cf_date
        )
        test_session.add(cf1)
        await test_session.flush()

        cf2 = CashFlowFactory.build(
            stock_id=stock.id, period=PeriodType.Q1, date=cf_date
        )
        test_session.add(cf2)

        with pytest.raises(IntegrityError) as exc_info:
            await test_session.flush()

        assert "unique" in str(exc_info.value).lower() or "duplicate" in str(exc_info.value).lower()


# --- Composite Primary Key Tests ---

class TestCompositePrimaryKeys:
    """Tests for composite primary keys."""

    @pytest.mark.asyncio
    async def test_watchlist_composite_pk(self, test_session: AsyncSession):
        """Watchlist should enforce composite primary key (user_id, stock_id)."""
        user = await create_user_async(test_session)
        stock = await create_stock_async(test_session, symbol="WCOMP")

        watchlist1 = WatchlistFactory.build(user_id=user.id, stock_id=stock.id)
        test_session.add(watchlist1)
        await test_session.flush()

        # Same user_id and stock_id should fail
        watchlist2 = WatchlistFactory.build(user_id=user.id, stock_id=stock.id)
        test_session.add(watchlist2)

        with pytest.raises(IntegrityError):
            await test_session.flush()

    @pytest.mark.asyncio
    async def test_user_news_composite_pk(self, test_session: AsyncSession):
        """UserNews should enforce composite primary key (user_id, news_id)."""
        user = await create_user_async(test_session)
        stock = await create_stock_async(test_session, symbol="UNCOMP")

        news = NewsFactory.build(stock_id=stock.id)
        test_session.add(news)
        await test_session.flush()

        user_news1 = UserNewsFactory.build(user_id=user.id, news_id=news.id)
        test_session.add(user_news1)
        await test_session.flush()

        # Same user_id and news_id should fail
        user_news2 = UserNewsFactory.build(user_id=user.id, news_id=news.id)
        test_session.add(user_news2)

        with pytest.raises(IntegrityError):
            await test_session.flush()

    @pytest.mark.asyncio
    async def test_stock_price_composite_pk(self, test_session: AsyncSession):
        """StockPrice should enforce composite primary key (stock_id, timestamp)."""
        stock = await create_stock_async(test_session, symbol="SPCOMP")
        ts = datetime.now(timezone.utc)

        price1 = StockPriceFactory.build(stock_id=stock.id, timestamp=ts)
        test_session.add(price1)
        await test_session.flush()

        # Same stock_id and timestamp should fail
        price2 = StockPriceFactory.build(stock_id=stock.id, timestamp=ts)
        test_session.add(price2)

        with pytest.raises(IntegrityError):
            await test_session.flush()

    @pytest.mark.asyncio
    async def test_document_chunk_composite_pk(self, test_session: AsyncSession):
        """DocumentChunk should have unique (kap_report_id, chunk_index)."""
        stock = await create_stock_async(test_session, symbol="DCCOMP")
        report = await create_kap_report_async(test_session, stock_id=stock.id)

        chunk1 = DocumentChunkFactory.build(kap_report_id=report.id, chunk_index=0)
        test_session.add(chunk1)
        await test_session.flush()

        # Same kap_report_id and chunk_index should fail
        chunk2 = DocumentChunkFactory.build(kap_report_id=report.id, chunk_index=0)
        test_session.add(chunk2)

        with pytest.raises(IntegrityError):
            await test_session.flush()


# --- Foreign Key Constraint Tests ---

class TestForeignKeyConstraints:
    """Tests for foreign key constraints."""

    @pytest.mark.asyncio
    async def test_fk_telegram_settings_user_must_exist(self, test_session: AsyncSession):
        """TelegramSettings user_id must reference existing user."""
        settings = TelegramSettingsFactory.build(user_id=99999)  # Non-existent user
        test_session.add(settings)

        with pytest.raises(IntegrityError):
            await test_session.flush()

    @pytest.mark.asyncio
    async def test_fk_watchlist_user_must_exist(self, test_session: AsyncSession):
        """Watchlist user_id must reference existing user."""
        stock = await create_stock_async(test_session, symbol="WFK")

        watchlist = WatchlistFactory.build(user_id=99999, stock_id=stock.id)
        test_session.add(watchlist)

        with pytest.raises(IntegrityError):
            await test_session.flush()

    @pytest.mark.asyncio
    async def test_fk_watchlist_stock_must_exist(self, test_session: AsyncSession):
        """Watchlist stock_id must reference existing stock."""
        user = await create_user_async(test_session)

        watchlist = WatchlistFactory.build(user_id=user.id, stock_id=99999)
        test_session.add(watchlist)

        with pytest.raises(IntegrityError):
            await test_session.flush()

    @pytest.mark.asyncio
    async def test_fk_balance_sheet_stock_must_exist(self, test_session: AsyncSession):
        """BalanceSheet stock_id must reference existing stock."""
        bs = BalanceSheetFactory.build(stock_id=99999)
        test_session.add(bs)

        with pytest.raises(IntegrityError):
            await test_session.flush()

    @pytest.mark.asyncio
    async def test_fk_chat_session_user_must_exist(self, test_session: AsyncSession):
        """ChatSession user_id must reference existing user."""
        session = ChatSessionFactory.build(user_id=99999)
        test_session.add(session)

        with pytest.raises(IntegrityError):
            await test_session.flush()

    @pytest.mark.asyncio
    async def test_fk_chat_message_session_must_exist(self, test_session: AsyncSession):
        """ChatMessage session_id must reference existing session."""
        message = ChatMessageFactory.build(session_id=99999)
        test_session.add(message)

        with pytest.raises(IntegrityError):
            await test_session.flush()

    @pytest.mark.asyncio
    async def test_fk_kap_report_stock_must_exist(self, test_session: AsyncSession):
        """KAPReport stock_id must reference existing stock."""
        report = KAPReportFactory.build(stock_id=99999)
        test_session.add(report)

        with pytest.raises(IntegrityError):
            await test_session.flush()

    @pytest.mark.asyncio
    async def test_fk_document_chunk_kap_report_must_exist(self, test_session: AsyncSession):
        """DocumentChunk kap_report_id must reference existing report."""
        chunk = DocumentChunkFactory.build(kap_report_id=99999)
        test_session.add(chunk)

        with pytest.raises(IntegrityError):
            await test_session.flush()


# --- NOT NULL Constraint Tests ---

class TestNotNullConstraints:
    """Tests for NOT NULL constraints."""

    @pytest.mark.asyncio
    async def test_user_username_not_null(self, test_session: AsyncSession):
        """User username should not be null."""
        user = UserFactory.build(username=None)
        test_session.add(user)

        with pytest.raises(IntegrityError):
            await test_session.flush()

    @pytest.mark.asyncio
    async def test_user_email_not_null(self, test_session: AsyncSession):
        """User email should not be null."""
        user = UserFactory.build(email=None)
        test_session.add(user)

        with pytest.raises(IntegrityError):
            await test_session.flush()

    @pytest.mark.asyncio
    async def test_user_password_hash_not_null(self, test_session: AsyncSession):
        """User password_hash should not be null."""
        user = UserFactory.build(password_hash=None)
        test_session.add(user)

        with pytest.raises(IntegrityError):
            await test_session.flush()

    @pytest.mark.asyncio
    async def test_stock_symbol_not_null(self, test_session: AsyncSession):
        """Stock symbol should not be null."""
        stock = StockFactory.build(symbol=None)
        test_session.add(stock)

        with pytest.raises(IntegrityError):
            await test_session.flush()

    @pytest.mark.asyncio
    async def test_stock_company_name_not_null(self, test_session: AsyncSession):
        """Stock company_name should not be null."""
        stock = StockFactory.build(company_name=None)
        test_session.add(stock)

        with pytest.raises(IntegrityError):
            await test_session.flush()

    @pytest.mark.asyncio
    async def test_kap_report_title_not_null(self, test_session: AsyncSession):
        """KAPReport title should not be null."""
        stock = await create_stock_async(test_session, symbol="KAPNOTNULL")
        report = KAPReportFactory.build(stock_id=stock.id, title=None)
        test_session.add(report)

        with pytest.raises(IntegrityError):
            await test_session.flush()

    @pytest.mark.asyncio
    async def test_news_title_not_null(self, test_session: AsyncSession):
        """News title should not be null."""
        news = NewsFactory.build(title=None)
        test_session.add(news)

        with pytest.raises(IntegrityError):
            await test_session.flush()

    @pytest.mark.asyncio
    async def test_news_content_not_null(self, test_session: AsyncSession):
        """News content should not be null."""
        news = NewsFactory.build(content=None)
        test_session.add(news)

        with pytest.raises(IntegrityError):
            await test_session.flush()

    @pytest.mark.asyncio
    async def test_chat_message_content_not_null(self, test_session: AsyncSession):
        """ChatMessage content should not be null."""
        user = await create_user_async(test_session)
        chat_session = await create_chat_session_async(test_session, user_id=user.id)

        message = ChatMessageFactory.build(session_id=chat_session.id, content=None)
        test_session.add(message)

        with pytest.raises(IntegrityError):
            await test_session.flush()


# --- Telegram Settings One-to-One Constraint Tests ---

class TestTelegramSettingsOneToOne:
    """Tests for TelegramSettings one-to-one relationship."""

    @pytest.mark.asyncio
    async def test_telegram_settings_user_id_is_primary_key(self, test_session: AsyncSession):
        """TelegramSettings user_id should be primary key (ensures one-to-one)."""
        user = await create_user_async(test_session)

        settings1 = TelegramSettingsFactory.build(user_id=user.id)
        test_session.add(settings1)
        await test_session.flush()

        # Second settings for same user should fail (PK violation)
        settings2 = TelegramSettingsFactory.build(user_id=user.id)
        test_session.add(settings2)

        with pytest.raises(IntegrityError):
            await test_session.flush()