"""
Integration tests for SQLAlchemy model relationships.

Tests verify:
- Cascade delete behavior
- Set null on delete
- Foreign key constraints
- Relationship loading
"""

import pytest
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

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
from app.models.enums import PeriodType, MessageRole, SyncStatus
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


# --- User Relationship Tests ---

class TestUserRelationships:
    """Tests for User model relationships."""

    @pytest.mark.asyncio
    async def test_user_telegram_settings_cascade_delete(self, test_session: AsyncSession):
        """Deleting user should cascade delete telegram_settings."""
        user = await create_user_async(test_session)

        settings = TelegramSettingsFactory.build(user_id=user.id)
        test_session.add(settings)
        await test_session.flush()

        user_id = user.id
        await test_session.delete(user)
        await test_session.flush()

        result = await test_session.execute(
            select(TelegramSettings).where(TelegramSettings.user_id == user_id)
        )
        assert result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_user_watchlist_cascade_delete(self, test_session: AsyncSession):
        """Deleting user should cascade delete watchlist entries."""
        user = await create_user_async(test_session)
        stock = await create_stock_async(test_session, symbol="WATCH")

        watchlist = WatchlistFactory.build(user_id=user.id, stock_id=stock.id)
        test_session.add(watchlist)
        await test_session.flush()

        user_id = user.id
        await test_session.delete(user)
        await test_session.flush()

        result = await test_session.execute(
            select(Watchlist).where(Watchlist.user_id == user_id)
        )
        assert result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_user_chat_sessions_cascade_delete(self, test_session: AsyncSession):
        """Deleting user should cascade delete chat sessions."""
        user = await create_user_async(test_session)
        session = await create_chat_session_async(test_session, user_id=user.id)

        user_id = user.id
        session_id = session.id

        await test_session.delete(user)
        await test_session.flush()

        result = await test_session.execute(
            select(ChatSession).where(ChatSession.id == session_id)
        )
        assert result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_user_news_read_status_cascade_delete(self, test_session: AsyncSession):
        """Deleting user should cascade delete user_news entries."""
        user = await create_user_async(test_session)
        stock = await create_stock_async(test_session, symbol="NEWSREL")

        news = NewsFactory.build(stock_id=stock.id)
        test_session.add(news)
        await test_session.flush()

        user_news = UserNewsFactory.build(user_id=user.id, news_id=news.id)
        test_session.add(user_news)
        await test_session.flush()

        user_id = user.id
        await test_session.delete(user)
        await test_session.flush()

        result = await test_session.execute(
            select(UserNews).where(UserNews.user_id == user_id)
        )
        assert result.scalar_one_or_none() is None


# --- Stock Relationship Tests ---

class TestStockRelationships:
    """Tests for Stock model relationships."""

    @pytest.mark.asyncio
    async def test_stock_prices_cascade_delete(self, test_session: AsyncSession):
        """Deleting stock should cascade delete prices."""
        stock = await create_stock_async(test_session, symbol="PRICEDEL")

        price = StockPriceFactory.build(stock_id=stock.id)
        test_session.add(price)
        await test_session.flush()

        stock_id = stock.id
        await test_session.delete(stock)
        await test_session.flush()

        result = await test_session.execute(
            select(StockPrice).where(StockPrice.stock_id == stock_id)
        )
        assert result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_stock_financials_cascade_delete(self, test_session: AsyncSession):
        """Deleting stock should cascade delete financial statements."""
        stock = await create_stock_async(test_session, symbol="FINDEL")

        bs = BalanceSheetFactory.build(stock_id=stock.id)
        inc = IncomeStatementFactory.build(stock_id=stock.id)
        cf = CashFlowFactory.build(stock_id=stock.id)
        test_session.add_all([bs, inc, cf])
        await test_session.flush()

        stock_id = stock.id
        await test_session.delete(stock)
        await test_session.flush()

        bs_result = await test_session.execute(
            select(BalanceSheet).where(BalanceSheet.stock_id == stock_id)
        )
        inc_result = await test_session.execute(
            select(IncomeStatement).where(IncomeStatement.stock_id == stock_id)
        )
        cf_result = await test_session.execute(
            select(CashFlow).where(CashFlow.stock_id == stock_id)
        )

        assert bs_result.scalar_one_or_none() is None
        assert inc_result.scalar_one_or_none() is None
        assert cf_result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_stock_kap_reports_cascade_delete(self, test_session: AsyncSession):
        """Deleting stock should cascade delete KAP reports."""
        stock = await create_stock_async(test_session, symbol="KAPDEL")
        report = await create_kap_report_async(test_session, stock_id=stock.id)

        stock_id = stock.id
        report_id = report.id

        await test_session.delete(stock)
        await test_session.flush()

        result = await test_session.execute(
            select(KAPReport).where(KAPReport.id == report_id)
        )
        assert result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_stock_news_items_cascade_delete(self, test_session: AsyncSession):
        """Deleting stock should cascade delete news items."""
        stock = await create_stock_async(test_session, symbol="NEWSDEL")

        news = NewsFactory.build(stock_id=stock.id)
        test_session.add(news)
        await test_session.flush()

        stock_id = stock.id
        await test_session.delete(stock)
        await test_session.flush()

        result = await test_session.execute(
            select(News).where(News.stock_id == stock_id)
        )
        assert result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_stock_pipeline_logs_set_null(self, test_session: AsyncSession):
        """Deleting stock should SET NULL on pipeline_logs."""
        stock = await create_stock_async(test_session, symbol="PIPESETNULL")

        log = PipelineLogFactory.build(stock_id=stock.id)
        test_session.add(log)
        await test_session.flush()

        log_id = log.id
        await test_session.delete(stock)
        await test_session.flush()

        result = await test_session.execute(
            select(PipelineLog).where(PipelineLog.id == log_id)
        )
        found_log = result.scalar_one_or_none()
        assert found_log is not None
        assert found_log.stock_id is None


# --- KAP Report Relationship Tests ---

class TestKAPReportRelationships:
    """Tests for KAPReport model relationships."""

    @pytest.mark.asyncio
    async def test_kap_report_document_chunks_cascade_delete(self, test_session: AsyncSession):
        """Deleting KAP report should cascade delete document chunks."""
        stock = await create_stock_async(test_session, symbol="DOCCASCADE")
        report = await create_kap_report_async(test_session, stock_id=stock.id)

        chunk = DocumentChunkFactory.build(kap_report_id=report.id)
        test_session.add(chunk)
        await test_session.flush()

        report_id = report.id
        await test_session.delete(report)
        await test_session.flush()

        result = await test_session.execute(
            select(DocumentChunk).where(DocumentChunk.kap_report_id == report_id)
        )
        assert result.scalar_one_or_none() is None


# --- Chat Relationship Tests ---

class TestChatRelationships:
    """Tests for ChatSession and ChatMessage relationships."""

    @pytest.mark.asyncio
    async def test_session_messages_cascade_delete(self, test_session: AsyncSession):
        """Deleting chat session should cascade delete messages."""
        user = await create_user_async(test_session)
        chat_session = await create_chat_session_async(test_session, user_id=user.id)

        message = ChatMessageFactory.build(session_id=chat_session.id)
        test_session.add(message)
        await test_session.flush()

        session_id = chat_session.id
        message_id = message.id

        await test_session.delete(chat_session)
        await test_session.flush()

        result = await test_session.execute(
            select(ChatMessage).where(ChatMessage.id == message_id)
        )
        assert result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_message_eval_logs_set_null(self, test_session: AsyncSession):
        """Deleting chat message should SET NULL on eval_logs."""
        user = await create_user_async(test_session)
        chat_session = await create_chat_session_async(test_session, user_id=user.id)

        message = ChatMessageFactory.build(session_id=chat_session.id)
        test_session.add(message)
        await test_session.flush()

        eval_log = EvalLogFactory.build(message_id=message.id)
        test_session.add(eval_log)
        await test_session.flush()

        eval_log_id = eval_log.id
        await test_session.delete(message)
        await test_session.flush()

        result = await test_session.execute(
            select(EvalLog).where(EvalLog.id == eval_log_id)
        )
        found_log = result.scalar_one_or_none()
        assert found_log is not None
        assert found_log.message_id is None


# --- Pipeline Log Relationship Tests ---

class TestPipelineLogRelationships:
    """Tests for PipelineLog model relationships."""

    @pytest.mark.asyncio
    async def test_pipeline_eval_logs_relationship(self, test_session: AsyncSession):
        """PipelineLog should have relationship to EvalLogs."""
        log = await create_pipeline_log_async(test_session)

        eval_log = EvalLogFactory.build(pipeline_run_id=log.run_id)
        test_session.add(eval_log)
        await test_session.flush()

        # Load relationship
        await test_session.refresh(log, ["eval_logs"])

        assert len(log.eval_logs) == 1
        assert log.eval_logs[0].pipeline_run_id == log.run_id

    @pytest.mark.asyncio
    async def test_pipeline_log_eval_logs_set_null_on_delete(self, test_session: AsyncSession):
        """Deleting PipelineLog should SET NULL on linked eval_logs."""
        log = await create_pipeline_log_async(test_session)

        eval_log = EvalLogFactory.build(pipeline_run_id=log.run_id)
        test_session.add(eval_log)
        await test_session.flush()

        eval_log_id = eval_log.id
        await test_session.delete(log)
        await test_session.flush()

        result = await test_session.execute(
            select(EvalLog).where(EvalLog.id == eval_log_id)
        )
        found_log = result.scalar_one_or_none()
        assert found_log is not None
        assert found_log.pipeline_run_id is None


# --- Eager Loading Tests ---

class TestRelationshipLoading:
    """Tests for relationship eager loading."""

    @pytest.mark.asyncio
    async def test_user_with_telegram_settings_eager_load(self, test_session: AsyncSession):
        """Should eagerly load user's telegram_settings."""
        user = await create_user_async(test_session)
        settings = TelegramSettingsFactory.build(user_id=user.id)
        test_session.add(settings)
        await test_session.flush()

        result = await test_session.execute(
            select(User)
            .where(User.id == user.id)
            .options(selectinload(User.telegram_settings))
        )
        loaded_user = result.scalar_one()

        assert loaded_user.telegram_settings is not None
        assert loaded_user.telegram_settings.user_id == user.id

    @pytest.mark.asyncio
    async def test_stock_with_prices_eager_load(self, test_session: AsyncSession):
        """Should eagerly load stock's prices."""
        stock = await create_stock_async(test_session, symbol="EAGERLOAD")

        # Use different timestamps to avoid composite PK violation
        price1 = StockPriceFactory.build(
            stock_id=stock.id,
            timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        )
        price2 = StockPriceFactory.build(
            stock_id=stock.id,
            timestamp=datetime(2024, 1, 2, 12, 0, 0, tzinfo=timezone.utc)
        )
        test_session.add_all([price1, price2])
        await test_session.flush()

        result = await test_session.execute(
            select(Stock)
            .where(Stock.id == stock.id)
            .options(selectinload(Stock.prices))
        )
        loaded_stock = result.scalar_one()

        assert len(loaded_stock.prices) == 2

    @pytest.mark.asyncio
    async def test_chat_session_with_messages_eager_load(self, test_session: AsyncSession):
        """Should eagerly load chat session's messages."""
        user = await create_user_async(test_session)
        chat_session = await create_chat_session_async(test_session, user_id=user.id)

        msg1 = ChatMessageFactory.build(session_id=chat_session.id)
        msg2 = ChatMessageFactory.build(session_id=chat_session.id)
        test_session.add_all([msg1, msg2])
        await test_session.flush()

        result = await test_session.execute(
            select(ChatSession)
            .where(ChatSession.id == chat_session.id)
            .options(selectinload(ChatSession.messages))
        )
        loaded_session = result.scalar_one()

        assert len(loaded_session.messages) == 2


# --- Bidirectional Relationship Tests ---

class TestBidirectionalRelationships:
    """Tests for bidirectional relationship sync."""

    @pytest.mark.asyncio
    async def test_user_telegram_settings_back_populates(self, test_session: AsyncSession):
        """User-TelegramSettings should back-populate correctly."""
        user = await create_user_async(test_session)
        settings = TelegramSettingsFactory.build(user_id=user.id)
        test_session.add(settings)
        await test_session.flush()

        await test_session.refresh(user, ["telegram_settings"])
        await test_session.refresh(settings, ["user"])

        assert user.telegram_settings is not None
        assert settings.user.id == user.id

    @pytest.mark.asyncio
    async def test_stock_kap_reports_back_populates(self, test_session: AsyncSession):
        """Stock-KAPReport should back-populate correctly."""
        stock = await create_stock_async(test_session, symbol="BIDIR")
        report = await create_kap_report_async(test_session, stock_id=stock.id)

        await test_session.refresh(stock, ["kap_reports"])
        await test_session.refresh(report, ["stock"])

        assert len(stock.kap_reports) == 1
        assert report.stock.id == stock.id

    @pytest.mark.asyncio
    async def test_chat_session_message_back_populates(self, test_session: AsyncSession):
        """ChatSession-ChatMessage should back-populate correctly."""
        user = await create_user_async(test_session)
        chat_session = await create_chat_session_async(test_session, user_id=user.id)

        message = ChatMessageFactory.build(session_id=chat_session.id)
        test_session.add(message)
        await test_session.flush()

        await test_session.refresh(chat_session, ["messages"])
        await test_session.refresh(message, ["session"])

        assert len(chat_session.messages) == 1
        assert message.session.id == chat_session.id