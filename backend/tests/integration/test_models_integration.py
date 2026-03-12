"""
Integration tests for SQLAlchemy ORM models with database.

These tests verify CRUD operations with actual database interaction.
Each test uses a transaction that rolls back after completion.
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
    PipelineLog,
    EvalLog,
)
from app.models.enums import (
    PeriodType,
    SyncStatus,
    NewsSource,
    MessageRole,
    MessageType,
    EmbeddingStatus,
    PipelineStatus,
)
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
    PipelineLogFactory,
    EvalLogFactory,
    create_user_async,
    create_stock_async,
    create_chat_session_async,
    create_kap_report_async,
    create_pipeline_log_async,
)


# --- User CRUD Tests ---

class TestUserCRUD:
    """CRUD operations for User model."""

    @pytest.mark.asyncio
    async def test_create_user(self, test_session: AsyncSession):
        """Should create a new user."""
        user = UserFactory.build(
            username="testuser",
            email="test@example.com",
            password_hash="hashed_password"
        )
        test_session.add(user)
        await test_session.flush()

        assert user.id is not None
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.notification_enabled is False

    @pytest.mark.asyncio
    async def test_read_user(self, test_session: AsyncSession):
        """Should read user from database."""
        user = await create_user_async(test_session, username="readuser")

        result = await test_session.execute(
            select(User).where(User.username == "readuser")
        )
        found_user = result.scalar_one()

        assert found_user.id == user.id
        assert found_user.username == "readuser"

    @pytest.mark.asyncio
    async def test_update_user(self, test_session: AsyncSession):
        """Should update user in database."""
        user = await create_user_async(test_session, username="updateuser")

        user.notification_enabled = True
        user.telegram_chat_id = "123456"
        await test_session.flush()

        await test_session.refresh(user)
        assert user.notification_enabled is True
        assert user.telegram_chat_id == "123456"

    @pytest.mark.asyncio
    async def test_delete_user(self, test_session: AsyncSession):
        """Should delete user from database."""
        user = await create_user_async(test_session, username="deleteuser")
        user_id = user.id

        await test_session.delete(user)
        await test_session.flush()

        result = await test_session.execute(
            select(User).where(User.id == user_id)
        )
        assert result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_user_email_unique(self, test_session: AsyncSession):
        """User email should be unique."""
        await create_user_async(test_session, email="unique@example.com")

        duplicate_user = UserFactory.build(email="unique@example.com")
        test_session.add(duplicate_user)

        with pytest.raises(IntegrityError):
            await test_session.flush()


# --- Stock CRUD Tests ---

class TestStockCRUD:
    """CRUD operations for Stock model."""

    @pytest.mark.asyncio
    async def test_create_stock(self, test_session: AsyncSession):
        """Should create a new stock."""
        stock = await create_stock_async(
            test_session,
            symbol="THYAO",
            yfinance_symbol="THYAO.IS"
        )

        assert stock.id is not None
        assert stock.symbol == "THYAO"
        assert stock.is_active is True

    @pytest.mark.asyncio
    async def test_read_stock(self, test_session: AsyncSession):
        """Should read stock from database."""
        stock = await create_stock_async(test_session, symbol="ASELS")

        result = await test_session.execute(
            select(Stock).where(Stock.symbol == "ASELS")
        )
        found_stock = result.scalar_one()

        assert found_stock.id == stock.id

    @pytest.mark.asyncio
    async def test_unique_symbol_violation(self, test_session: AsyncSession):
        """Stock symbol should be unique."""
        await create_stock_async(test_session, symbol="GARAN")

        duplicate_stock = StockFactory.build(symbol="GARAN", yfinance_symbol="GARAN2.IS")
        test_session.add(duplicate_stock)

        with pytest.raises(IntegrityError):
            await test_session.flush()

    @pytest.mark.asyncio
    async def test_soft_delete_is_active(self, test_session: AsyncSession):
        """Stock should support soft delete via is_active."""
        stock = await create_stock_async(test_session, symbol="SOFTDEL")

        stock.is_active = False
        await test_session.flush()

        await test_session.refresh(stock)
        assert stock.is_active is False


# --- Watchlist CRUD Tests ---

class TestWatchlistCRUD:
    """CRUD operations for Watchlist model."""

    @pytest.mark.asyncio
    async def test_create_watchlist_entry(self, test_session: AsyncSession):
        """Should create watchlist entry."""
        user = await create_user_async(test_session)
        stock = await create_stock_async(test_session, symbol="WATCH")

        watchlist = WatchlistFactory.build(user_id=user.id, stock_id=stock.id)
        test_session.add(watchlist)
        await test_session.flush()

        assert watchlist.user_id == user.id
        assert watchlist.stock_id == stock.id

    @pytest.mark.asyncio
    async def test_watchlist_composite_pk_unique(self, test_session: AsyncSession):
        """Watchlist should prevent duplicate user-stock pairs."""
        user = await create_user_async(test_session)
        stock = await create_stock_async(test_session, symbol="WLIST")

        watchlist1 = WatchlistFactory.build(user_id=user.id, stock_id=stock.id)
        test_session.add(watchlist1)
        await test_session.flush()

        watchlist2 = WatchlistFactory.build(user_id=user.id, stock_id=stock.id)
        test_session.add(watchlist2)

        with pytest.raises(IntegrityError):
            await test_session.flush()


# --- Stock Price CRUD Tests ---

class TestStockPriceCRUD:
    """CRUD operations for StockPrice model."""

    @pytest.mark.asyncio
    async def test_create_stock_price(self, test_session: AsyncSession):
        """Should create stock price entry."""
        stock = await create_stock_async(test_session, symbol="PRICE")

        price = StockPriceFactory.build(
            stock_id=stock.id,
            timestamp=datetime.now(timezone.utc)
        )
        test_session.add(price)
        await test_session.flush()

        assert price.stock_id == stock.id
        assert price.close is not None

    @pytest.mark.asyncio
    async def test_stock_price_composite_pk(self, test_session: AsyncSession):
        """StockPrice should have composite primary key."""
        stock = await create_stock_async(test_session, symbol="PRICE2")
        ts = datetime.now(timezone.utc)

        price1 = StockPriceFactory.build(stock_id=stock.id, timestamp=ts)
        test_session.add(price1)
        await test_session.flush()

        # Same stock_id and timestamp should fail
        price2 = StockPriceFactory.build(stock_id=stock.id, timestamp=ts)
        test_session.add(price2)

        with pytest.raises(IntegrityError):
            await test_session.flush()


# --- Financial Statement CRUD Tests ---

class TestBalanceSheetCRUD:
    """CRUD operations for BalanceSheet model."""

    @pytest.mark.asyncio
    async def test_create_balance_sheet(self, test_session: AsyncSession):
        """Should create balance sheet entry."""
        stock = await create_stock_async(test_session, symbol="BAL")

        balance_sheet = BalanceSheetFactory.build(
            stock_id=stock.id,
            period=PeriodType.Q1,
            date=date.today()
        )
        test_session.add(balance_sheet)
        await test_session.flush()

        assert balance_sheet.id is not None
        assert balance_sheet.period == PeriodType.Q1

    @pytest.mark.asyncio
    async def test_unique_stock_period_date(self, test_session: AsyncSession):
        """BalanceSheet should have unique (stock_id, period, date)."""
        stock = await create_stock_async(test_session, symbol="BAL2")
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

        with pytest.raises(IntegrityError):
            await test_session.flush()


class TestIncomeStatementCRUD:
    """CRUD operations for IncomeStatement model."""

    @pytest.mark.asyncio
    async def test_create_income_statement(self, test_session: AsyncSession):
        """Should create income statement entry."""
        stock = await create_stock_async(test_session, symbol="INC")

        income_stmt = IncomeStatementFactory.build(
            stock_id=stock.id,
            period=PeriodType.Q2,
            date=date.today()
        )
        test_session.add(income_stmt)
        await test_session.flush()

        assert income_stmt.id is not None
        assert income_stmt.revenue is not None


class TestCashFlowCRUD:
    """CRUD operations for CashFlow model."""

    @pytest.mark.asyncio
    async def test_create_cash_flow(self, test_session: AsyncSession):
        """Should create cash flow entry."""
        stock = await create_stock_async(test_session, symbol="CF")

        cash_flow = CashFlowFactory.build(
            stock_id=stock.id,
            period=PeriodType.ANNUAL,
            date=date.today()
        )
        test_session.add(cash_flow)
        await test_session.flush()

        assert cash_flow.id is not None
        assert cash_flow.operating_cash_flow is not None


# --- KAP Report CRUD Tests ---

class TestKAPReportCRUD:
    """CRUD operations for KAPReport model."""

    @pytest.mark.asyncio
    async def test_create_kap_report(self, test_session: AsyncSession):
        """Should create KAP report entry."""
        stock = await create_stock_async(test_session, symbol="KAP")
        report = await create_kap_report_async(
            test_session,
            stock_id=stock.id,
            bildirim_no="KAP-001"
        )

        assert report.id is not None
        assert report.bildirim_no == "KAP-001"
        assert report.chroma_sync_status == SyncStatus.PENDING

    @pytest.mark.asyncio
    async def test_bildirim_no_unique(self, test_session: AsyncSession):
        """KAPReport bildirim_no should be unique."""
        stock = await create_stock_async(test_session, symbol="KAP2")

        await create_kap_report_async(test_session, stock_id=stock.id, bildirim_no="UNIQUE-001")

        duplicate = KAPReportFactory.build(bildirim_no="UNIQUE-001")
        test_session.add(duplicate)

        with pytest.raises(IntegrityError):
            await test_session.flush()


# --- News CRUD Tests ---

class TestNewsCRUD:
    """CRUD operations for News model."""

    @pytest.mark.asyncio
    async def test_create_news(self, test_session: AsyncSession):
        """Should create news entry."""
        stock = await create_stock_async(test_session, symbol="NEWS")

        news = NewsFactory.build(
            stock_id=stock.id,
            title="Test News",
            source_type=NewsSource.KAP_SUMMARY
        )
        test_session.add(news)
        await test_session.flush()

        assert news.id is not None
        assert news.title == "Test News"

    @pytest.mark.asyncio
    async def test_news_without_stock(self, test_session: AsyncSession):
        """News should allow null stock_id for general market news."""
        news = NewsFactory.build(
            stock_id=None,
            title="General Market News",
            source_type=NewsSource.EXTERNAL_NEWS
        )
        test_session.add(news)
        await test_session.flush()

        assert news.id is not None
        assert news.stock_id is None


class TestUserNewsCRUD:
    """CRUD operations for UserNews model."""

    @pytest.mark.asyncio
    async def test_create_user_news(self, test_session: AsyncSession):
        """Should create user news entry."""
        user = await create_user_async(test_session)
        stock = await create_stock_async(test_session, symbol="UN")

        news = NewsFactory.build(stock_id=stock.id)
        test_session.add(news)
        await test_session.flush()

        user_news = UserNewsFactory.build(user_id=user.id, news_id=news.id)
        test_session.add(user_news)
        await test_session.flush()

        assert user_news.user_id == user.id
        assert user_news.news_id == news.id
        assert user_news.is_read is False


# --- Chat CRUD Tests ---

class TestChatSessionCRUD:
    """CRUD operations for ChatSession model."""

    @pytest.mark.asyncio
    async def test_create_chat_session(self, test_session: AsyncSession):
        """Should create chat session."""
        user = await create_user_async(test_session)
        session = await create_chat_session_async(test_session, user_id=user.id)

        assert session.id is not None
        assert session.user_id == user.id

    @pytest.mark.asyncio
    async def test_read_chat_session(self, test_session: AsyncSession):
        """Should read chat session."""
        user = await create_user_async(test_session)
        session = await create_chat_session_async(
            test_session, user_id=user.id, title="Test Chat"
        )

        result = await test_session.execute(
            select(ChatSession).where(ChatSession.id == session.id)
        )
        found = result.scalar_one()

        assert found.title == "Test Chat"


class TestChatMessageCRUD:
    """CRUD operations for ChatMessage model."""

    @pytest.mark.asyncio
    async def test_create_chat_message(self, test_session: AsyncSession):
        """Should create chat message."""
        user = await create_user_async(test_session)
        chat_session = await create_chat_session_async(test_session, user_id=user.id)

        message = ChatMessageFactory.build(
            session_id=chat_session.id,
            role=MessageRole.USER,
            content="Hello!"
        )
        test_session.add(message)
        await test_session.flush()

        assert message.id is not None
        assert message.content == "Hello!"
        assert message.role == MessageRole.USER


# --- Document Chunk CRUD Tests ---

class TestDocumentChunkCRUD:
    """CRUD operations for DocumentChunk model."""

    @pytest.mark.asyncio
    async def test_create_document_chunk(self, test_session: AsyncSession):
        """Should create document chunk."""
        stock = await create_stock_async(test_session, symbol="DOC")
        report = await create_kap_report_async(test_session, stock_id=stock.id)

        chunk = DocumentChunkFactory.build(
            kap_report_id=report.id,
            chunk_index=0
        )
        test_session.add(chunk)
        await test_session.flush()

        assert chunk.id is not None
        assert chunk.embedding_status == EmbeddingStatus.PENDING


# --- Pipeline Log CRUD Tests ---

class TestPipelineLogCRUD:
    """CRUD operations for PipelineLog model."""

    @pytest.mark.asyncio
    async def test_create_pipeline_log(self, test_session: AsyncSession):
        """Should create pipeline log."""
        log = await create_pipeline_log_async(
            test_session,
            pipeline_name="test_pipeline",
            status=PipelineStatus.RUNNING
        )

        assert log.id is not None
        assert log.run_id is not None
        assert log.status == PipelineStatus.RUNNING

    @pytest.mark.asyncio
    async def test_pipeline_log_with_stock(self, test_session: AsyncSession):
        """PipelineLog should allow optional stock_id."""
        stock = await create_stock_async(test_session, symbol="PIPE")

        log = PipelineLogFactory.build(
            pipeline_name="stock_sync",
            stock_id=stock.id
        )
        test_session.add(log)
        await test_session.flush()

        assert log.stock_id == stock.id


# --- Eval Log CRUD Tests ---

class TestEvalLogCRUD:
    """CRUD operations for EvalLog model."""

    @pytest.mark.asyncio
    async def test_create_eval_log(self, test_session: AsyncSession):
        """Should create eval log."""
        log = EvalLogFactory.build(
            bert_score=Decimal("0.8500"),
            is_hallucinated=False
        )
        test_session.add(log)
        await test_session.flush()

        assert log.id is not None
        assert log.bert_score == Decimal("0.8500")

    @pytest.mark.asyncio
    async def test_eval_log_with_message(self, test_session: AsyncSession):
        """EvalLog should link to ChatMessage."""
        user = await create_user_async(test_session)
        chat_session = await create_chat_session_async(test_session, user_id=user.id)

        message = ChatMessageFactory.build(session_id=chat_session.id)
        test_session.add(message)
        await test_session.flush()

        eval_log = EvalLogFactory.build(message_id=message.id)
        test_session.add(eval_log)
        await test_session.flush()

        assert eval_log.message_id == message.id


# --- Telegram Settings CRUD Tests ---

class TestTelegramSettingsCRUD:
    """CRUD operations for TelegramSettings model."""

    @pytest.mark.asyncio
    async def test_create_telegram_settings(self, test_session: AsyncSession):
        """Should create telegram settings for user."""
        user = await create_user_async(test_session)

        settings = TelegramSettingsFactory.build(user_id=user.id)
        test_session.add(settings)
        await test_session.flush()

        assert settings.user_id == user.id
        assert settings.notification_times is not None

    @pytest.mark.asyncio
    async def test_telegram_settings_one_to_one(self, test_session: AsyncSession):
        """User should have at most one TelegramSettings."""
        user = await create_user_async(test_session)

        settings1 = TelegramSettingsFactory.build(user_id=user.id)
        test_session.add(settings1)
        await test_session.flush()

        settings2 = TelegramSettingsFactory.build(user_id=user.id)
        test_session.add(settings2)

        with pytest.raises(IntegrityError):
            await test_session.flush()