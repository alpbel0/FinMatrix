"""Unit tests for the Code Executor agent (Task 6.3)."""

import sys
from datetime import date
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add borsapy to path
borsapy_path = Path(__file__).parent.parent.parent.parent / "search" / "borsapy"
if borsapy_path.exists():
    sys.path.insert(0, str(borsapy_path.parent))

from app.services.agents.code_executor import (
    build_code_executor_agent,
    compute_pe_from_snapshot,
    debt_to_equity,
    get_financial_history,
    get_latest_financials,
    get_previous_financials,
    net_profit_growth,
    roe,
    run_numerical_analysis,
    safe_divide,
)


# ============================================================================
# Helper: build a mock Result object that chains scalar_one_or_none()
# ============================================================================


def _mock_result(value: Any) -> MagicMock:
    """Return a mock Result whose scalar_one_or_none() returns `value`."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


# ============================================================================
# Helper tests (no I/O)
# ============================================================================


class TestSafeDivide:
    def test_normal(self):
        assert safe_divide(10.0, 2.0) == pytest.approx(5.0)

    def test_zero_denominator(self):
        assert safe_divide(10.0, 0.0) is None

    def test_none_numerator(self):
        assert safe_divide(None, 2.0) is None

    def test_none_denominator(self):
        assert safe_divide(10.0, None) is None

    def test_negative_denominator(self):
        assert safe_divide(10.0, -2.0) == pytest.approx(-5.0)


class TestNetProfitGrowth:
    def test_normal_positive(self):
        assert net_profit_growth(120.0, 100.0) == pytest.approx(0.2)

    def test_normal_negative(self):
        assert net_profit_growth(80.0, 100.0) == pytest.approx(-0.2)

    def test_zero_previous(self):
        assert net_profit_growth(100.0, 0.0) is None

    def test_none_current(self):
        assert net_profit_growth(None, 100.0) is None

    def test_none_previous(self):
        assert net_profit_growth(100.0, None) is None

    def test_100_percent_growth(self):
        assert net_profit_growth(200.0, 100.0) == pytest.approx(1.0)


class TestRoe:
    def test_normal(self):
        assert roe(50.0, 200.0) == pytest.approx(0.25)

    def test_zero_equity(self):
        assert roe(50.0, 0.0) is None

    def test_none_equity(self):
        assert roe(50.0, None) is None

    def test_none_income(self):
        assert roe(None, 200.0) is None


class TestDebtToEquity:
    def test_normal(self):
        assert debt_to_equity(300.0, 200.0) == pytest.approx(0.5)

    def test_zero_equity(self):
        assert debt_to_equity(300.0, 0.0) is None

    def test_none_equity(self):
        assert debt_to_equity(300.0, None) is None

    def test_negative_debt(self):
        # total_assets < total_equity → negative debt
        assert debt_to_equity(100.0, 200.0) == pytest.approx(-0.5)


class TestComputePeFromSnapshot:
    def test_uses_pe_ratio(self):
        pe, warn = compute_pe_from_snapshot(pe_ratio=8.5, market_cap=None, net_income=100.0)
        assert pe == 8.5
        assert warn is None

    def test_fallback_market_cap_positive_income(self):
        pe, warn = compute_pe_from_snapshot(
            pe_ratio=None, market_cap=1_000_000.0, net_income=100_000.0
        )
        assert pe == pytest.approx(10.0)
        assert warn is None

    def test_negative_income_returns_none(self):
        pe, warn = compute_pe_from_snapshot(
            pe_ratio=None, market_cap=1_000_000.0, net_income=-50_000.0
        )
        assert pe is None
        assert "P/E hesaplanamadı" in warn

    def test_zero_income_returns_none(self):
        pe, warn = compute_pe_from_snapshot(
            pe_ratio=None, market_cap=1_000_000.0, net_income=0.0
        )
        assert pe is None
        assert "P/E hesaplanamadı" in warn

    def test_no_pe_ratio_no_market_cap(self):
        pe, warn = compute_pe_from_snapshot(
            pe_ratio=None, market_cap=None, net_income=100_000.0
        )
        assert pe is None
        assert "P/E hesaplanamadı" in warn

    def test_pe_ratio_zero_or_negative_not_used(self):
        pe, warn = compute_pe_from_snapshot(
            pe_ratio=0.0, market_cap=1_000_000.0, net_income=100_000.0
        )
        assert pe == pytest.approx(10.0)  # falls back to market_cap
        assert warn is None


# ============================================================================
# DB helper tests (mock db)
# ============================================================================


class TestGetLatestFinancials:
    @pytest.mark.asyncio
    async def test_annual_returns_latest(self):
        """get_latest_financials returns the most recent annual row."""
        mock_inc = MagicMock()
        mock_inc.stock_id = 1
        mock_inc.period_type = "annual"
        mock_inc.statement_date = date(2024, 12, 31)
        mock_inc.revenue = 1_000.0
        mock_inc.net_income = 100.0
        mock_inc.source = "borsapy"

        mock_bs = MagicMock()
        mock_bs.total_assets = 5_000.0
        mock_bs.total_equity = 2_000.0

        mock_db = AsyncMock()
        # First execute → income statement; second execute → balance sheet
        mock_db.execute.side_effect = [
            _mock_result(mock_inc),  # latest income
            _mock_result(mock_bs),   # matching balance sheet
        ]

        inc_out, bs_out = await get_latest_financials(
            mock_db, stock_id=1, period_type=MagicMock(value="annual")
        )
        assert inc_out == mock_inc
        assert bs_out == mock_bs

    @pytest.mark.asyncio
    async def test_no_income_statement_returns_none_tuple(self):
        """When no income statement found, returns (None, None)."""
        mock_db = AsyncMock()
        mock_db.execute.side_effect = [_mock_result(None)]

        inc_out, bs_out = await get_latest_financials(mock_db, stock_id=1)
        assert inc_out is None
        assert bs_out is None


class TestGetPreviousFinancials:
    @pytest.mark.asyncio
    async def test_returns_prior_period(self):
        """get_previous_financials returns the row before current_date."""
        mock_inc = MagicMock()
        mock_inc.stock_id = 1
        mock_inc.period_type = "annual"
        mock_inc.statement_date = date(2023, 12, 31)
        mock_inc.net_income = 80.0

        mock_bs = MagicMock()

        mock_db = AsyncMock()
        mock_db.execute.side_effect = [_mock_result(mock_inc), _mock_result(mock_bs)]

        inc_out, _ = await get_previous_financials(
            mock_db,
            stock_id=1,
            period_type=MagicMock(value="annual"),
            current_date=date(2024, 12, 31),
        )
        assert inc_out == mock_inc


class TestGetFinancialHistory:
    @pytest.mark.asyncio
    async def test_returns_ordered_list_with_limit(self):
        """get_financial_history returns rows ordered DESC with limit."""
        mock_row1 = MagicMock(statement_date=date(2024, 12, 31), net_income=100.0)
        mock_row2 = MagicMock(statement_date=date(2023, 12, 31), net_income=80.0)
        mock_row3 = MagicMock(statement_date=date(2022, 12, 31), net_income=60.0)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_row1, mock_row2, mock_row3]

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        history = await get_financial_history(mock_db, stock_id=1, limit=3)
        assert len(history) == 3


# ============================================================================
# Integration-style tests (mock db + mock borsapy)
# ============================================================================


class TestRunNumericalAnalysisSingleSymbol:
    @pytest.mark.asyncio
    async def test_single_symbol_returns_metrics_no_comparison(self):
        """Single symbol: result has metrics, comparison_table is None."""
        mock_inc = MagicMock()
        mock_inc.stock_id = 1
        mock_inc.period_type = "annual"
        mock_inc.statement_date = date(2024, 12, 31)
        mock_inc.revenue = 1_000.0
        mock_inc.net_income = 100.0
        mock_inc.source = "borsapy"

        mock_bs = MagicMock()
        mock_bs.total_assets = 5_000.0
        mock_bs.total_equity = 2_000.0

        mock_db = AsyncMock()
        mock_db.execute.side_effect = [
            _mock_result("THYAO"),       # Stock.symbol lookup
            _mock_result(1),              # Stock.id lookup
            _mock_result(mock_inc),       # latest income
            _mock_result(mock_bs),        # matching balance sheet
            _mock_result(None),           # previous income (none)
        ]

        mock_snapshot = MagicMock()
        mock_snapshot.pe_ratio = 8.5
        mock_snapshot.market_cap = None

        with patch(
            "app.services.agents.code_executor.BorsapyProvider"
        ) as MockBorsapy:
            mock_provider = MagicMock()
            mock_provider.get_stock_snapshot.return_value = mock_snapshot
            MockBorsapy.return_value = mock_provider

            result = await run_numerical_analysis(
                db=mock_db, query="THYAO ROE nedir?", symbols=["THYAO"]
            )

        assert len(result.metrics) == 1
        assert result.metrics[0].symbol == "THYAO"
        assert result.metrics[0].net_income == 100.0
        assert result.metrics[0].roe == pytest.approx(0.05)
        assert result.metrics[0].debt_to_equity == pytest.approx(1.5)
        assert result.metrics[0].pe_ratio == pytest.approx(8.5)
        assert result.comparison_table is None
        assert result.insufficient_data is False


class TestRunNumericalAnalysisMultiSymbol:
    @pytest.mark.asyncio
    async def test_multi_symbol_returns_comparison_table(self):
        """Multi symbol: result has comparison_table."""
        mock_inc_thyao = MagicMock()
        mock_inc_thyao.stock_id = 1
        mock_inc_thyao.period_type = "annual"
        mock_inc_thyao.statement_date = date(2024, 12, 31)
        mock_inc_thyao.revenue = 1_000.0
        mock_inc_thyao.net_income = 100.0
        mock_inc_thyao.source = "borsapy"

        mock_bs_thyao = MagicMock()
        mock_bs_thyao.total_assets = 5_000.0
        mock_bs_thyao.total_equity = 2_000.0

        mock_inc_asels = MagicMock()
        mock_inc_asels.stock_id = 2
        mock_inc_asels.period_type = "annual"
        mock_inc_asels.statement_date = date(2024, 12, 31)
        mock_inc_asels.revenue = 500.0
        mock_inc_asels.net_income = 50.0
        mock_inc_asels.source = "borsapy"

        mock_bs_asels = MagicMock()
        mock_bs_asels.total_assets = 2_500.0
        mock_bs_asels.total_equity = 1_000.0

        mock_db = AsyncMock()
        mock_db.execute.side_effect = [
            # THYAO
            _mock_result("THYAO"),        # symbol lookup
            _mock_result(1),              # id lookup
            # ASELS
            _mock_result("ASELS"),        # symbol lookup
            _mock_result(2),              # id lookup
            # THYAO financials
            _mock_result(mock_inc_thyao), # latest income
            _mock_result(mock_bs_thyao),  # balance sheet
            _mock_result(None),           # previous income
            # ASELS financials
            _mock_result(mock_inc_asels), # latest income
            _mock_result(mock_bs_asels),  # balance sheet
            _mock_result(None),           # previous income
        ]

        mock_snapshot_thyao = MagicMock()
        mock_snapshot_thyao.pe_ratio = 8.5
        mock_snapshot_thyao.market_cap = None

        mock_snapshot_asels = MagicMock()
        mock_snapshot_asels.pe_ratio = 10.0
        mock_snapshot_asels.market_cap = None

        with patch(
            "app.services.agents.code_executor.BorsapyProvider"
        ) as MockBorsapy:
            mock_provider = MagicMock()
            mock_provider.get_stock_snapshot.side_effect = [
                mock_snapshot_thyao,
                mock_snapshot_asels,
            ]
            MockBorsapy.return_value = mock_provider

            result = await run_numerical_analysis(
                db=mock_db,
                query="THYAO vs ASELS karşılaştırması",
                symbols=["THYAO", "ASELS"],
            )

        assert len(result.metrics) == 2
        assert result.comparison_table is not None
        metric_names = [row.metric for row in result.comparison_table]
        assert "Net Kar" in metric_names
        assert "Hasılat" in metric_names
        assert "ROE" in metric_names
        assert "P/E" in metric_names
        assert "Debt/Equity" in metric_names


        assert result.metrics[0].pe_ratio == pytest.approx(8.5)
        assert result.metrics[1].pe_ratio == pytest.approx(10.0)


class TestComparisonTableRows:
    @pytest.mark.asyncio
    async def test_single_symbol_no_comparison_table(self):
        """Single symbol: comparison_table is None."""
        mock_inc = MagicMock()
        mock_inc.stock_id = 1
        mock_inc.period_type = "annual"
        mock_inc.statement_date = date(2024, 12, 31)
        mock_inc.revenue = 1_000.0
        mock_inc.net_income = 100.0
        mock_inc.source = "borsapy"

        mock_bs = MagicMock()
        mock_bs.total_assets = 5_000.0
        mock_bs.total_equity = 2_000.0

        mock_db = AsyncMock()
        mock_db.execute.side_effect = [
            _mock_result("THYAO"),
            _mock_result(1),
            _mock_result(mock_inc),
            _mock_result(mock_bs),
            _mock_result(None),
        ]

        mock_snapshot = MagicMock()
        mock_snapshot.pe_ratio = 8.5
        mock_snapshot.market_cap = None

        with patch(
            "app.services.agents.code_executor.BorsapyProvider"
        ) as MockBorsapy:
            mock_provider = MagicMock()
            mock_provider.get_stock_snapshot.return_value = mock_snapshot
            MockBorsapy.return_value = mock_provider

            result = await run_numerical_analysis(
                db=mock_db, query="THYAO analizi", symbols=["THYAO"]
            )

        assert result.comparison_table is None


class TestPeRatioFromSnapshot:
    @pytest.mark.asyncio
    async def test_pe_ratio_uses_snapshot_pe_ratio(self):
        """When snapshot has pe_ratio > 0, it is used."""
        mock_inc = MagicMock()
        mock_inc.stock_id = 1
        mock_inc.period_type = "annual"
        mock_inc.statement_date = date(2024, 12, 31)
        mock_inc.revenue = 1_000.0
        mock_inc.net_income = 100.0
        mock_inc.source = "borsapy"

        mock_bs = MagicMock()
        mock_bs.total_assets = 5_000.0
        mock_bs.total_equity = 2_000.0

        mock_db = AsyncMock()
        mock_db.execute.side_effect = [
            _mock_result("THYAO"),
            _mock_result(1),
            _mock_result(mock_inc),
            _mock_result(mock_bs),
            _mock_result(None),
        ]

        mock_snapshot = MagicMock()
        mock_snapshot.pe_ratio = 8.5
        mock_snapshot.market_cap = None

        with patch(
            "app.services.agents.code_executor.BorsapyProvider"
        ) as MockBorsapy:
            mock_provider = MagicMock()
            mock_provider.get_stock_snapshot.return_value = mock_snapshot
            MockBorsapy.return_value = mock_provider

            result = await run_numerical_analysis(
                db=mock_db, query="THYAO", symbols=["THYAO"]
            )

        # P/E should not appear as a warning
        pe_warnings = [w for w in result.warnings if "P/E" in w]
        assert len(pe_warnings) == 0

    @pytest.mark.asyncio
    async def test_pe_ratio_fallback_to_market_cap(self):
        """When pe_ratio not available but market_cap is, use market_cap / net_income."""
        mock_inc = MagicMock()
        mock_inc.stock_id = 1
        mock_inc.period_type = "annual"
        mock_inc.statement_date = date(2024, 12, 31)
        mock_inc.revenue = 1_000.0
        mock_inc.net_income = 100_000.0
        mock_inc.source = "borsapy"

        mock_bs = MagicMock()
        mock_bs.total_assets = 5_000.0
        mock_bs.total_equity = 2_000.0

        mock_db = AsyncMock()
        mock_db.execute.side_effect = [
            _mock_result("THYAO"),
            _mock_result(1),
            _mock_result(mock_inc),
            _mock_result(mock_bs),
            _mock_result(None),
        ]

        mock_snapshot = MagicMock()
        mock_snapshot.pe_ratio = None
        mock_snapshot.market_cap = 1_000_000.0  # 1M / 100K = 10

        with patch(
            "app.services.agents.code_executor.BorsapyProvider"
        ) as MockBorsapy:
            mock_provider = MagicMock()
            mock_provider.get_stock_snapshot.return_value = mock_snapshot
            MockBorsapy.return_value = mock_provider

            result = await run_numerical_analysis(
                db=mock_db, query="THYAO", symbols=["THYAO"]
            )

        pe_warnings = [w for w in result.warnings if "P/E" in w]
        assert len(pe_warnings) == 0

    @pytest.mark.asyncio
    async def test_pe_ratio_warning_on_failure(self):
        """When borsapy get_stock_snapshot fails, warning is added but result still returns."""
        mock_inc = MagicMock()
        mock_inc.stock_id = 1
        mock_inc.period_type = "annual"
        mock_inc.statement_date = date(2024, 12, 31)
        mock_inc.revenue = 1_000.0
        mock_inc.net_income = 100.0
        mock_inc.source = "borsapy"

        mock_bs = MagicMock()
        mock_bs.total_assets = 5_000.0
        mock_bs.total_equity = 2_000.0

        mock_db = AsyncMock()
        mock_db.execute.side_effect = [
            _mock_result("THYAO"),
            _mock_result(1),
            _mock_result(mock_inc),
            _mock_result(mock_bs),
            _mock_result(None),
        ]

        with patch(
            "app.services.agents.code_executor.BorsapyProvider"
        ) as MockBorsapy:
            mock_provider = MagicMock()
            mock_provider.get_stock_snapshot.side_effect = Exception("Network error")
            MockBorsapy.return_value = mock_provider

            result = await run_numerical_analysis(
                db=mock_db, query="THYAO", symbols=["THYAO"]
            )

        snapshot_warnings = [w for w in result.warnings if "snapshot" in w.lower()]
        assert len(snapshot_warnings) > 0
        # Result should still be returned
        assert result.metrics[0].symbol == "THYAO"


class TestChartPayload:
    @pytest.mark.asyncio
    async def test_chart_payload_net_income_series(self):
        """When needs_chart=True, chart payload contains net_income series."""
        mock_inc = MagicMock()
        mock_inc.stock_id = 1
        mock_inc.period_type = "annual"
        mock_inc.statement_date = date(2024, 12, 31)
        mock_inc.revenue = 1_000.0
        mock_inc.net_income = 100.0
        mock_inc.source = "borsapy"

        mock_bs = MagicMock()
        mock_bs.total_assets = 5_000.0
        mock_bs.total_equity = 2_000.0

        mock_history_rows = [
            MagicMock(statement_date=date(2024, 12, 31), net_income=100.0),
            MagicMock(statement_date=date(2023, 12, 31), net_income=80.0),
            MagicMock(statement_date=date(2022, 12, 31), net_income=60.0),
        ]

        mock_history_result = MagicMock()
        mock_history_result.scalars.return_value.all.return_value = mock_history_rows

        mock_db = AsyncMock()
        mock_db.execute.side_effect = [
            _mock_result("THYAO"),       # symbol lookup
            _mock_result(1),              # id lookup
            _mock_result(mock_inc),       # latest income
            _mock_result(mock_bs),        # balance sheet
            _mock_result(None),           # previous income
            mock_history_result,          # financial history
        ]

        mock_snapshot = MagicMock()
        mock_snapshot.pe_ratio = 8.5
        mock_snapshot.market_cap = None

        with patch(
            "app.services.agents.code_executor.BorsapyProvider"
        ) as MockBorsapy:
            mock_provider = MagicMock()
            mock_provider.get_stock_snapshot.return_value = mock_snapshot
            MockBorsapy.return_value = mock_provider

            result = await run_numerical_analysis(
                db=mock_db,
                query="THYAO net kar grafiği",
                symbols=["THYAO"],
                needs_chart=True,
            )

        assert result.chart is not None
        assert result.chart.type == "line"
        assert "Net Kar" in result.chart.title
        assert len(result.chart.series) == 1
        assert result.chart.series[0].name == "Net Kar"
        assert len(result.chart.series[0].data) == 3

    @pytest.mark.asyncio
    async def test_no_chart_when_needs_chart_false(self):
        """When needs_chart=False, chart is None."""
        mock_inc = MagicMock()
        mock_inc.stock_id = 1
        mock_inc.period_type = "annual"
        mock_inc.statement_date = date(2024, 12, 31)
        mock_inc.revenue = 1_000.0
        mock_inc.net_income = 100.0
        mock_inc.source = "borsapy"

        mock_bs = MagicMock()
        mock_bs.total_assets = 5_000.0
        mock_bs.total_equity = 2_000.0

        mock_db = AsyncMock()
        mock_db.execute.side_effect = [
            _mock_result("THYAO"),
            _mock_result(1),
            _mock_result(mock_inc),
            _mock_result(mock_bs),
            _mock_result(None),
        ]

        mock_snapshot = MagicMock()
        mock_snapshot.pe_ratio = 8.5
        mock_snapshot.market_cap = None

        with patch(
            "app.services.agents.code_executor.BorsapyProvider"
        ) as MockBorsapy:
            mock_provider = MagicMock()
            mock_provider.get_stock_snapshot.return_value = mock_snapshot
            MockBorsapy.return_value = mock_provider

            result = await run_numerical_analysis(
                db=mock_db, query="THYAO", symbols=["THYAO"], needs_chart=False
            )

        assert result.chart is None


class TestInsufficientData:
    @pytest.mark.asyncio
    async def test_insufficient_data_true_when_no_rows(self):
        """When no financial data exists for any symbol, insufficient_data=True."""
        mock_db = AsyncMock()
        mock_db.execute.return_value = _mock_result(None)

        result = await run_numerical_analysis(
            db=mock_db, query="X9999 analizi", symbols=["X9999"]
        )

        assert result.insufficient_data is True
        assert len(result.metrics) == 0


class TestPartialDataWarning:
    @pytest.mark.asyncio
    async def test_partial_data_warning(self):
        """When some fields are missing, result still returns."""
        mock_inc = MagicMock()
        mock_inc.stock_id = 1
        mock_inc.period_type = "annual"
        mock_inc.statement_date = date(2024, 12, 31)
        mock_inc.revenue = 1_000.0
        mock_inc.net_income = None  # missing
        mock_inc.source = "borsapy"

        mock_bs = MagicMock()
        mock_bs.total_assets = 5_000.0
        mock_bs.total_equity = None  # missing

        mock_db = AsyncMock()
        mock_db.execute.side_effect = [
            _mock_result("THYAO"),
            _mock_result(1),
            _mock_result(mock_inc),
            _mock_result(mock_bs),
            _mock_result(None),
        ]

        mock_snapshot = MagicMock()
        mock_snapshot.pe_ratio = None
        mock_snapshot.market_cap = None

        with patch(
            "app.services.agents.code_executor.BorsapyProvider"
        ) as MockBorsapy:
            mock_provider = MagicMock()
            mock_provider.get_stock_snapshot.return_value = mock_snapshot
            MockBorsapy.return_value = mock_provider

            result = await run_numerical_analysis(
                db=mock_db, query="THYAO", symbols=["THYAO"]
            )

        # Should still return result (partial data)
        assert len(result.metrics) == 1
        assert result.metrics[0].net_income is None
        assert result.metrics[0].total_equity is None
        assert any("net_income eksik" in warning for warning in result.warnings)
        assert any("total_equity eksik" in warning for warning in result.warnings)


class TestBuildCodeExecutorAgent:
    def test_build_code_executor_agent_returns_agent_or_spec(self):
        """build_code_executor_agent returns a CrewAgentSpec or CrewAI Agent."""
        agent = build_code_executor_agent()
        assert agent is not None
        assert hasattr(agent, "role")
        assert agent.role == "FinMatrix Code Executor"
