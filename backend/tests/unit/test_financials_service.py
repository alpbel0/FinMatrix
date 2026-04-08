"""Unit tests for financials_service.

Tests the service layer with mocked providers and database operations.
"""

import pytest
from datetime import date, datetime
from unittest.mock import patch, MagicMock
import uuid

from sqlalchemy import select

from app.models.stock import Stock
from app.models.pipeline_log import PipelineLog
from app.services.financials_service import (
    FinancialSyncResult,
    FinancialBatchSyncResult,
    sync_financial_statements,
    sync_all_financial_statements,
    batch_sync_financials,
    validate_quarterly_net_income,
)
from app.services.data.provider_models import PeriodType, FinancialStatementSet
from app.services.data.provider_exceptions import (
    ProviderConnectionError,
    ProviderRateLimitError,
    ProviderSymbolNotFoundError,
)
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
            net_income=5e9,
        ),
        create_financial_statement_set(
            symbol="THYAO",
            period_type=PeriodType.ANNUAL,
            statement_date=date(2023, 12, 31),
            net_income=4.5e9,
        ),
    ]


@pytest.fixture
def sample_quarterly_statements():
    """Create sample quarterly financial statements (8 quarters)."""
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
                net_income=1e9 + i * 0.1e9,
            )
        )
    return statements


# ============================================================================
# validate_quarterly_net_income Tests
# ============================================================================


class TestValidateQuarterlyNetIncome:
    """Tests for validate_quarterly_net_income function."""

    def test_valid_quarters_returns_empty_warnings(self, sample_quarterly_statements):
        """Valid quarters should return empty warnings list."""
        warnings = validate_quarterly_net_income(sample_quarterly_statements, required_count=8)
        assert warnings == []

    def test_missing_quarters_returns_warning(self):
        """Missing quarters should return warning."""
        # Only 5 quarters instead of 8
        statements = [
            create_financial_statement_set(
                period_type=PeriodType.QUARTERLY,
                statement_date=date(2024, 9, 30),
                net_income=1e9,
            )
            for _ in range(5)
        ]
        warnings = validate_quarterly_net_income(statements, required_count=8)
        assert len(warnings) == 1
        assert "Only 5 quarters" in warnings[0]

    def test_missing_net_income_returns_warning(self):
        """Missing net_income should return warning."""
        statements = []
        quarters = [
            date(2024, 9, 30), date(2024, 6, 30), date(2024, 3, 31), date(2023, 12, 31),
            date(2023, 9, 30), date(2023, 6, 30), date(2023, 3, 31), date(2022, 12, 31),
        ]
        for i, q_date in enumerate(quarters):
            statements.append(
                create_financial_statement_set(
                    period_type=PeriodType.QUARTERLY,
                    statement_date=q_date,
                    net_income=None if i == 0 else 1e9,  # First quarter missing net_income
                )
            )
        warnings = validate_quarterly_net_income(statements, required_count=8)
        assert len(warnings) == 1
        assert "Missing net_income" in warnings[0]

    def test_custom_required_count(self):
        """Should respect custom required_count parameter."""
        statements = [
            create_financial_statement_set(
                period_type=PeriodType.QUARTERLY,
                net_income=1e9,
            )
            for _ in range(4)
        ]
        warnings = validate_quarterly_net_income(statements, required_count=4)
        assert warnings == []

        warnings = validate_quarterly_net_income(statements, required_count=8)
        assert len(warnings) == 1


# ============================================================================
# sync_financial_statements Tests
# ============================================================================


class TestSyncFinancialStatements:
    """Tests for sync_financial_statements function."""

    @pytest.mark.asyncio
    async def test_sync_annual_success(self, db_session, mock_provider, sample_annual_statements):
        """Successful annual sync should return correct result."""
        stock = Stock(symbol="THYAO", company_name="Test", is_active=True)
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
        assert result.quarterly_count == 0

    @pytest.mark.asyncio
    async def test_sync_quarterly_with_validation(self, db_session, mock_provider, sample_quarterly_statements):
        """Quarterly sync should validate net_income."""
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
                validate_quarterly=True,
            )

        assert result.success is True
        assert result.quarterly_count == 8
        assert result.validation_warnings == []

    @pytest.mark.asyncio
    async def test_sync_quarterly_validation_warnings(self, db_session, mock_provider):
        """Quarterly sync should include validation warnings."""
        stock = Stock(symbol="THYAO", company_name="Test", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        # Only 5 quarters with one missing net_income
        statements = [
            create_financial_statement_set(
                period_type=PeriodType.QUARTERLY,
                statement_date=date(2024, 9 - i, 30) if 9 - i >= 1 else date(2023, 12, 31),
                net_income=None if i == 0 else 1e9,
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
        assert len(result.validation_warnings) > 0

    @pytest.mark.asyncio
    async def test_sync_handles_stock_not_found(self, db_session, mock_provider):
        """Should return failed result for unknown symbol."""
        with patch(
            "app.services.financials_service.get_provider_for_financials",
            return_value=mock_provider
        ):
            result = await sync_financial_statements(
                db_session, "INVALID",
                period_type=PeriodType.ANNUAL,
            )

        assert result.success is False
        assert "not found" in result.error_message.lower()
        mock_provider.get_financial_statements.assert_not_called()

    @pytest.mark.asyncio
    async def test_sync_handles_empty_data(self, db_session, mock_provider):
        """Empty statements should succeed with 0 count."""
        stock = Stock(symbol="THYAO", company_name="Test", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        mock_provider.get_financial_statements.return_value = []

        with patch(
            "app.services.financials_service.get_provider_for_financials",
            return_value=mock_provider
        ):
            result = await sync_financial_statements(
                db_session, "THYAO",
                period_type=PeriodType.ANNUAL,
            )

        assert result.success is True
        assert result.total_statements == 0

    @pytest.mark.asyncio
    async def test_sync_handles_provider_symbol_not_found(self, db_session, mock_provider):
        """ProviderSymbolNotFoundError should return failed result."""
        stock = Stock(symbol="INVALID", company_name="Test", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        mock_provider.get_financial_statements.side_effect = ProviderSymbolNotFoundError("INVALID")

        with patch(
            "app.services.financials_service.get_provider_for_financials",
            return_value=mock_provider
        ):
            result = await sync_financial_statements(
                db_session, "INVALID",
                period_type=PeriodType.ANNUAL,
            )

        assert result.success is False

    @pytest.mark.asyncio
    async def test_sync_retries_on_connection_error(self, db_session, mock_provider, sample_annual_statements):
        """Should retry on ProviderConnectionError."""
        stock = Stock(symbol="THYAO", company_name="Test", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        # Fail once, then succeed
        mock_provider.get_financial_statements.side_effect = [
            ProviderConnectionError("Connection failed"),
            sample_annual_statements,
        ]

        with patch(
            "app.services.financials_service.get_provider_for_financials",
            return_value=mock_provider
        ):
            result = await sync_financial_statements(
                db_session, "THYAO",
                period_type=PeriodType.ANNUAL,
            )

        assert result.success is True
        assert mock_provider.get_financial_statements.call_count == 2

    @pytest.mark.asyncio
    async def test_sync_normalizes_symbol(self, db_session, mock_provider, sample_annual_statements):
        """Symbol should be normalized to uppercase."""
        stock = Stock(symbol="THYAO", company_name="Test", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        mock_provider.get_financial_statements.return_value = sample_annual_statements

        with patch(
            "app.services.financials_service.get_provider_for_financials",
            return_value=mock_provider
        ):
            result = await sync_financial_statements(
                db_session, "thyao",  # lowercase
                period_type=PeriodType.ANNUAL,
            )

        assert result.symbol == "THYAO"

    @pytest.mark.asyncio
    async def test_sync_fails_when_statement_persistence_fails(self, db_session, mock_provider, sample_annual_statements):
        """Persistence failures should fail the sync instead of returning fake success."""
        stock = Stock(symbol="THYAO", company_name="Test", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        mock_provider.get_financial_statements.return_value = sample_annual_statements

        with patch(
            "app.services.financials_service.get_provider_for_financials",
            return_value=mock_provider
        ), patch(
            "app.services.financials_service.upsert_financial_statement_set",
            side_effect=RuntimeError("db write failed")
        ):
            result = await sync_financial_statements(
                db_session, "THYAO",
                period_type=PeriodType.ANNUAL,
                validate_quarterly=False,
            )

        assert result.success is False
        assert "Failed to persist statements" in result.error_message

    @pytest.mark.asyncio
    async def test_rate_limit_does_not_consume_retry_budget(self, db_session, mock_provider, sample_annual_statements):
        """Rate limit waits should not consume retry attempts."""
        stock = Stock(symbol="THYAO", company_name="Test", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        rate_limit_error = ProviderRateLimitError("Slow down")
        rate_limit_error.retry_after = 0
        mock_provider.get_financial_statements.side_effect = [
            rate_limit_error,
            ProviderConnectionError("Connection failed"),
            sample_annual_statements,
        ]

        with patch(
            "app.services.financials_service.get_provider_for_financials",
            return_value=mock_provider
        ):
            result = await sync_financial_statements(
                db_session, "THYAO",
                period_type=PeriodType.ANNUAL,
                validate_quarterly=False,
            )

        assert result.success is True
        assert mock_provider.get_financial_statements.call_count == 3


# ============================================================================
# sync_all_financial_statements Tests
# ============================================================================


class TestSyncAllFinancialStatements:
    """Tests for sync_all_financial_statements function."""

    @pytest.mark.asyncio
    async def test_syncs_both_annual_and_quarterly(self, db_session, mock_provider, sample_annual_statements, sample_quarterly_statements):
        """Should sync both annual and quarterly statements."""
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
            )

        assert result.success is True
        assert result.annual_count == 2
        assert result.quarterly_count == 8
        assert result.total_statements == 10

    @pytest.mark.asyncio
    async def test_aggregates_errors(self, db_session, mock_provider):
        """Should aggregate errors from both syncs."""
        stock = Stock(symbol="THYAO", company_name="Test", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        # Both fail
        mock_provider.get_financial_statements.side_effect = ProviderConnectionError("Failed")

        with patch(
            "app.services.financials_service.get_provider_for_financials",
            return_value=mock_provider
        ):
            result = await sync_all_financial_statements(db_session, "THYAO")

        assert result.success is False
        assert result.error_message is not None


# ============================================================================
# batch_sync_financials Tests
# ============================================================================


class TestBatchSyncFinancials:
    """Tests for batch_sync_financials function."""

    @pytest.mark.asyncio
    async def test_batch_sync_creates_pipeline_log(self, db_session, mock_provider, sample_annual_statements):
        """Should create PipelineLog entry."""
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
            )

        # Verify PipelineLog was created
        log_result = await db_session.execute(
            select(PipelineLog).where(PipelineLog.run_id == result.run_id)
        )
        log = log_result.scalar_one_or_none()

        assert log is not None
        assert log.pipeline_name == "financials_sync"

    @pytest.mark.asyncio
    async def test_batch_sync_partial_success(self, db_session, mock_provider, sample_annual_statements):
        """Partial success should have status='partial'."""
        for symbol in ["THYAO", "GARAN"]:
            stock = Stock(symbol=symbol, company_name=f"{symbol} Company", is_active=True)
            db_session.add(stock)
        await db_session.commit()

        def mock_get_financials(symbol, **kwargs):
            if symbol == "THYAO":
                return sample_annual_statements
            raise ProviderSymbolNotFoundError(symbol)

        mock_provider.get_financial_statements.side_effect = mock_get_financials

        with patch(
            "app.services.financials_service.get_provider_for_financials",
            return_value=mock_provider
        ):
            result = await batch_sync_financials(
                db_session, ["THYAO", "GARAN"],
                period_type=PeriodType.ANNUAL,
            )

        assert result.status == "partial"
        assert "THYAO" in result.successful
        assert len(result.failed) == 1

    @pytest.mark.asyncio
    async def test_batch_sync_stores_details(self, db_session, mock_provider, sample_annual_statements):
        """Should store period_type and last_n in details."""
        stock = Stock(symbol="THYAO", company_name="Test", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        mock_provider.get_financial_statements.return_value = sample_annual_statements

        with patch(
            "app.services.financials_service.get_provider_for_financials",
            return_value=mock_provider
        ):
            result = await batch_sync_financials(
                db_session, ["THYAO"],
                period_type=PeriodType.QUARTERLY,
                last_n=8,
            )

        assert result.details is not None
        assert result.details["period_type"] == "quarterly"
        assert result.details["last_n"] == 8


# ============================================================================
# FinancialSyncResult Model Tests
# ============================================================================


class TestFinancialSyncResultModel:
    """Tests for FinancialSyncResult Pydantic model."""

    def test_default_values(self):
        """Should have correct default values."""
        result = FinancialSyncResult(symbol="THYAO", success=True)
        assert result.annual_count == 0
        assert result.quarterly_count == 0
        assert result.total_statements == 0
        assert result.validation_warnings == []
        assert result.error_message is None

    def test_with_validation_warnings(self):
        """Should accept validation warnings."""
        result = FinancialSyncResult(
            symbol="THYAO",
            success=True,
            validation_warnings=["Missing net_income for Q3"],
        )
        assert len(result.validation_warnings) == 1


class TestFinancialBatchSyncResultModel:
    """Tests for FinancialBatchSyncResult Pydantic model."""

    def test_status_values(self):
        """Status should be explicitly set."""
        result = FinancialBatchSyncResult(
            pipeline_name="test",
            run_id=str(uuid.uuid4()),
            status="partial",
            started_at=datetime.now(),
            finished_at=datetime.now(),
            total_statements=5,
            successful=["THYAO"],
            failed=[],
        )
        assert result.status == "partial"
