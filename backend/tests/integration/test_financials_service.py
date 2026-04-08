"""Integration tests for financials_service.

Tests with real database session but mocked provider.
"""

import pytest
from datetime import date
from unittest.mock import patch, MagicMock

from sqlalchemy import select

from app.models.stock import Stock
from app.models.income_statement import IncomeStatement
from app.models.balance_sheet import BalanceSheet
from app.models.cash_flow import CashFlow
from app.models.pipeline_log import PipelineLog
from app.services.financials_service import (
    sync_financial_statements,
    sync_all_financial_statements,
    batch_sync_financials,
    validate_quarterly_net_income,
)
from app.services.data.provider_models import PeriodType
from tests.factories import create_financial_statement_set


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_provider():
    """Create a mock provider for testing."""
    provider = MagicMock()
    provider.get_financial_statements = MagicMock()
    return provider


@pytest.fixture
def sample_annual_statements():
    """Create sample annual financial statements."""
    return [
        create_financial_statement_set(
            symbol="THYAO",
            period_type=PeriodType.ANNUAL,
            statement_date=date(2024, 12, 31),
            revenue=50e9,
            net_income=5e9,
            total_assets=100e9,
            total_equity=50e9,
            operating_cash_flow=6e9,
            free_cash_flow=4e9,
        ),
        create_financial_statement_set(
            symbol="THYAO",
            period_type=PeriodType.ANNUAL,
            statement_date=date(2023, 12, 31),
            revenue=48e9,
            net_income=4.5e9,
            total_assets=95e9,
            total_equity=48e9,
            operating_cash_flow=5.5e9,
            free_cash_flow=3.5e9,
        ),
    ]


@pytest.fixture
def sample_quarterly_statements():
    """Create sample quarterly financial statements."""
    statements = []
    quarters = [
        date(2024, 9, 30), date(2024, 6, 30), date(2024, 3, 31), date(2023, 12, 31),
        date(2023, 9, 30), date(2023, 6, 30), date(2023, 3, 31), date(2022, 12, 31),
    ]
    for i, q_date in enumerate(quarters):
        statements.append(
            create_financial_statement_set(
                symbol="THYAO",
                period_type=PeriodType.QUARTERLY,
                statement_date=q_date,
                revenue=12e9 + i * 0.5e9,
                net_income=1e9 + i * 0.1e9,
                total_assets=100e9,
                total_equity=50e9,
                operating_cash_flow=1.5e9,
                free_cash_flow=1e9,
            )
        )
    return statements


# ============================================================================
# sync_financial_statements Integration Tests
# ============================================================================


class TestSyncFinancialStatementsIntegration:
    """Integration tests for sync_financial_statements with real database."""

    @pytest.mark.asyncio
    async def test_sync_annual_persists_to_all_tables(self, db_session, mock_provider, sample_annual_statements):
        """Annual statements should persist to all 3 financial tables."""
        # Create stock
        stock = Stock(symbol="THYAO", company_name="Turk Hava Yollari", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        mock_provider.get_financial_statements.return_value = sample_annual_statements

        with patch(
            "app.services.financials_service.get_provider_for_financials",
            return_value=mock_provider
        ):
            result = await sync_financial_statements(
                db_session, "THYAO",
                period_type=PeriodType.ANNUAL,
                last_n=5,
                validate_quarterly=False,
            )

        assert result.success is True
        assert result.annual_count == 2

        # Verify income_statements persisted
        income_result = await db_session.execute(
            select(IncomeStatement)
            .where(IncomeStatement.stock_id == stock.id)
            .where(IncomeStatement.period_type == "annual")
        )
        income_records = list(income_result.scalars().all())
        assert len(income_records) == 2

        # Verify balance_sheets persisted
        balance_result = await db_session.execute(
            select(BalanceSheet)
            .where(BalanceSheet.stock_id == stock.id)
            .where(BalanceSheet.period_type == "annual")
        )
        balance_records = list(balance_result.scalars().all())
        assert len(balance_records) == 2

        # Verify cash_flows persisted
        cashflow_result = await db_session.execute(
            select(CashFlow)
            .where(CashFlow.stock_id == stock.id)
            .where(CashFlow.period_type == "annual")
        )
        cashflow_records = list(cashflow_result.scalars().all())
        assert len(cashflow_records) == 2

    @pytest.mark.asyncio
    async def test_sync_quarterly_persists_with_correct_period(self, db_session, mock_provider, sample_quarterly_statements):
        """Quarterly statements should have period_type='quarterly'."""
        # Create stock
        stock = Stock(symbol="THYAO", company_name="Test", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        mock_provider.get_financial_statements.return_value = sample_quarterly_statements

        with patch(
            "app.services.financials_service.get_provider_for_financials",
            return_value=mock_provider
        ):
            result = await sync_financial_statements(
                db_session, "THYAO",
                period_type=PeriodType.QUARTERLY,
                last_n=8,
                validate_quarterly=False,
            )

        assert result.success is True
        assert result.quarterly_count == 8

        # Verify period_type
        income_result = await db_session.execute(
            select(IncomeStatement)
            .where(IncomeStatement.stock_id == stock.id)
        )
        for record in income_result.scalars().all():
            assert record.period_type == "quarterly"

    @pytest.mark.asyncio
    async def test_sync_upserts_existing_statements(self, db_session, mock_provider, sample_annual_statements):
        """Upsert should update existing statement records."""
        # Create stock
        stock = Stock(symbol="THYAO", company_name="Test", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        # First sync with original values
        mock_provider.get_financial_statements.return_value = sample_annual_statements

        with patch(
            "app.services.financials_service.get_provider_for_financials",
            return_value=mock_provider
        ):
            await sync_financial_statements(
                db_session, "THYAO",
                period_type=PeriodType.ANNUAL,
                validate_quarterly=False,
            )

        # Second sync with updated revenue
        updated_statements = [
            create_financial_statement_set(
                period_type=PeriodType.ANNUAL,
                statement_date=date(2024, 12, 31),
                revenue=60e9,  # Updated from 50e9
                net_income=5e9,
            ),
        ]
        mock_provider.get_financial_statements.return_value = updated_statements

        with patch(
            "app.services.financials_service.get_provider_for_financials",
            return_value=mock_provider
        ):
            await sync_financial_statements(
                db_session, "THYAO",
                period_type=PeriodType.ANNUAL,
                validate_quarterly=False,
            )

        # Verify only 2 records (not 3) and revenue updated
        income_result = await db_session.execute(
            select(IncomeStatement)
            .where(IncomeStatement.stock_id == stock.id)
            .where(IncomeStatement.statement_date == date(2024, 12, 31))
        )
        record = income_result.scalar_one()
        assert record.revenue == 60e9

    @pytest.mark.asyncio
    async def test_sync_validates_quarterly_net_income(self, db_session, mock_provider):
        """Quarterly sync should validate net_income for last 8 quarters."""
        # Create stock
        stock = Stock(symbol="THYAO", company_name="Test", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        # Only 5 quarters
        statements = [
            create_financial_statement_set(
                period_type=PeriodType.QUARTERLY,
                statement_date=date(2024, 9 - i, 30) if 9 - i >= 1 else date(2023, 12, 31),
                net_income=1e9,
            )
            for i in range(5)
        ]
        mock_provider.get_financial_statements.return_value = statements

        with patch(
            "app.services.financials_service.get_provider_for_financials",
            return_value=mock_provider
        ):
            result = await sync_financial_statements(
                db_session, "THYAO",
                period_type=PeriodType.QUARTERLY,
                last_n=8,
                validate_quarterly=True,
            )

        assert result.success is True
        assert len(result.validation_warnings) == 1
        assert "Only 5 quarters" in result.validation_warnings[0]


# ============================================================================
# sync_all_financial_statements Integration Tests
# ============================================================================


class TestSyncAllFinancialStatementsIntegration:
    """Integration tests for sync_all_financial_statements."""

    @pytest.mark.asyncio
    async def test_syncs_both_types_to_database(self, db_session, mock_provider, sample_annual_statements, sample_quarterly_statements):
        """Should sync both annual and quarterly to database."""
        # Create stock
        stock = Stock(symbol="THYAO", company_name="Test", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        def mock_get_financials(symbol, period_type, last_n):
            if period_type == PeriodType.ANNUAL:
                return sample_annual_statements
            return sample_quarterly_statements

        mock_provider.get_financial_statements.side_effect = mock_get_financials

        with patch(
            "app.services.financials_service.get_provider_for_financials",
            return_value=mock_provider
        ):
            result = await sync_all_financial_statements(
                db_session, "THYAO",
                annual_last_n=5,
                quarterly_last_n=8,
                validate_quarterly=False,
            )

        assert result.success is True
        assert result.annual_count == 2
        assert result.quarterly_count == 8

        # Verify both annual and quarterly in database
        annual_count = await db_session.execute(
            select(IncomeStatement)
            .where(IncomeStatement.stock_id == stock.id)
            .where(IncomeStatement.period_type == "annual")
        )
        assert len(list(annual_count.scalars().all())) == 2

        quarterly_count = await db_session.execute(
            select(IncomeStatement)
            .where(IncomeStatement.stock_id == stock.id)
            .where(IncomeStatement.period_type == "quarterly")
        )
        assert len(list(quarterly_count.scalars().all())) == 8


# ============================================================================
# batch_sync_financials Integration Tests
# ============================================================================


class TestBatchSyncFinancialsIntegration:
    """Integration tests for batch_sync_financials with real database."""

    @pytest.mark.asyncio
    async def test_batch_sync_creates_pipeline_log(self, db_session, mock_provider, sample_annual_statements):
        """PipelineLog should be persisted with correct details."""
        # Create stocks
        for symbol in ["THYAO", "GARAN"]:
            stock = Stock(symbol=symbol, company_name=f"{symbol} Company", is_active=True)
            db_session.add(stock)
        await db_session.commit()

        mock_provider.get_financial_statements.return_value = sample_annual_statements

        with patch(
            "app.services.financials_service.get_provider_for_financials",
            return_value=mock_provider
        ):
            result = await batch_sync_financials(
                db_session, ["THYAO", "GARAN"],
                period_type=PeriodType.ANNUAL,
                last_n=5,
            )

        # Verify PipelineLog persisted
        log_result = await db_session.execute(
            select(PipelineLog).where(PipelineLog.run_id == result.run_id)
        )
        saved_log = log_result.scalar_one()

        assert saved_log.pipeline_name == "financials_sync"
        assert saved_log.status == "success"
        assert saved_log.details["period_type"] == "annual"
        assert saved_log.details["last_n"] == 5
        assert "THYAO" in saved_log.details["successful_symbols"]
        assert "GARAN" in saved_log.details["successful_symbols"]

    @pytest.mark.asyncio
    async def test_batch_sync_persists_all_data(self, db_session, mock_provider, sample_annual_statements):
        """All data should be persisted for all symbols."""
        # Create stocks
        for symbol in ["THYAO", "GARAN"]:
            stock = Stock(symbol=symbol, company_name=f"{symbol} Company", is_active=True)
            db_session.add(stock)
        await db_session.commit()

        mock_provider.get_financial_statements.return_value = sample_annual_statements

        with patch(
            "app.services.financials_service.get_provider_for_financials",
            return_value=mock_provider
        ):
            result = await batch_sync_financials(
                db_session, ["THYAO", "GARAN"],
                period_type=PeriodType.ANNUAL,
                last_n=5,
            )

        assert result.total_statements == 4  # 2 statements * 2 symbols

        # Verify data for both stocks
        for symbol in ["THYAO", "GARAN"]:
            stock_result = await db_session.execute(
                select(Stock).where(Stock.symbol == symbol)
            )
            stock = stock_result.scalar_one()
            income_result = await db_session.execute(
                select(IncomeStatement).where(IncomeStatement.stock_id == stock.id)
            )
            assert len(list(income_result.scalars().all())) == 2


# ============================================================================
# validate_quarterly_net_income Integration Tests
# ============================================================================


class TestValidateQuarterlyNetIncomeIntegration:
    """Integration tests for validate_quarterly_net_income."""

    def test_returns_warnings_for_missing_data(self):
        """Should return warnings when data is incomplete."""
        quarters = [
            date(2024, 9, 30), date(2024, 6, 30), date(2024, 3, 31), date(2023, 12, 31),
            date(2023, 9, 30), date(2023, 6, 30), date(2023, 3, 31), date(2022, 12, 31),
        ]
        statements = [
            create_financial_statement_set(
                period_type=PeriodType.QUARTERLY,
                statement_date=quarters[i],
                net_income=None if i % 2 == 0 else 1e9,  # Every other quarter missing net_income
            )
            for i in range(8)
        ]

        warnings = validate_quarterly_net_income(statements, required_count=8)

        assert len(warnings) == 1
        assert "Missing net_income" in warnings[0]


# ============================================================================
# End-to-End Financials Sync Flow Tests
# ============================================================================


class TestFinancialsSyncEndToEnd:
    """End-to-end tests for financials sync flow."""

    @pytest.mark.asyncio
    async def test_full_sync_flow(self, db_session, mock_provider):
        """Test complete sync flow from stock creation to database persistence."""
        # Step 1: Create stock
        stock = Stock(symbol="THYAO", company_name="Turk Hava Yollari", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        # Step 2: Prepare mock data
        statements = [
            create_financial_statement_set(
                period_type=PeriodType.ANNUAL,
                statement_date=date(2024 - i, 12, 31),
                revenue=50e9 - i * 2e9,
                net_income=5e9 - i * 0.5e9,
                total_assets=100e9 - i * 5e9,
                total_equity=50e9 - i * 2e9,
            )
            for i in range(5)
        ]
        mock_provider.get_financial_statements.return_value = statements

        # Step 3: Run sync
        with patch(
            "app.services.financials_service.get_provider_for_financials",
            return_value=mock_provider
        ):
            result = await sync_financial_statements(
                db_session, "THYAO",
                period_type=PeriodType.ANNUAL,
                last_n=5,
                validate_quarterly=False,
            )

        # Step 4: Verify results
        assert result.success is True
        assert result.annual_count == 5

        # Step 5: Verify all three tables have data
        income_result = await db_session.execute(
            select(IncomeStatement)
            .where(IncomeStatement.stock_id == stock.id)
            .order_by(IncomeStatement.statement_date.desc())
        )
        income_records = list(income_result.scalars().all())
        assert len(income_records) == 5
        assert income_records[0].statement_date == date(2024, 12, 31)

        balance_result = await db_session.execute(
            select(BalanceSheet).where(BalanceSheet.stock_id == stock.id)
        )
        assert len(list(balance_result.scalars().all())) == 5

        cashflow_result = await db_session.execute(
            select(CashFlow).where(CashFlow.stock_id == stock.id)
        )
        assert len(list(cashflow_result.scalars().all())) == 5