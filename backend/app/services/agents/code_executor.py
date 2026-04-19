"""CrewAI-ready Code Executor for numerical / financial queries.

This agent handles queries that require calculations (ROE, P/E, growth, comparison).
It uses deterministic code — no LLM reasoning — and reads from:
  - income_statements + balance_sheets DB tables
  - borsapy live snapshot for P/E ratio

Flow:
  1. resolve_symbol() → canonical symbol → stock_id
  2. get_latest_financials() → current period (income + balance)
  3. get_previous_financials() → prior period (for growth calc)
  4. borsapy get_stock_snapshot() → P/E from pe_ratio or market_cap/net_income
  5. Build NumericalAnalysisResult (metrics, comparison_table, chart)
"""

from datetime import date
from functools import lru_cache
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.balance_sheet import BalanceSheet
from app.models.income_statement import IncomeStatement
from app.models.stock import Stock
from app.schemas.chat import (
    ChartPayload,
    ChartSeries,
    ComparisonTableRow,
    FinancialMetricSnapshot,
    NumericalAnalysisResult,
)
from app.services.agents.crewai_adapter import create_agent_or_spec
from app.services.agents.symbol_resolver import resolve_symbol
from app.services.data.provider_models import PeriodType
from app.services.data.providers.borsapy_provider import BorsapyProvider
from app.services.utils.logging import logger


# ============================================================================
# Deterministic metric helpers
# ============================================================================


def safe_divide(numerator: float | None, denominator: float | None) -> float | None:
    """Return numerator / denominator or None if denominator is 0 or None."""
    if denominator is None or denominator == 0:
        return None
    if numerator is None:
        return None
    return numerator / denominator


def net_profit_growth(current: float | None, previous: float | None) -> float | None:
    """Return (current - previous) / |previous| or None if previous is 0 or None."""
    if current is None or previous is None or previous == 0:
        return None
    return (current - previous) / abs(previous)


def roe(net_income: float | None, total_equity: float | None) -> float | None:
    """Return net_income / total_equity or None."""
    return safe_divide(net_income, total_equity)


def debt_to_equity(total_assets: float | None, total_equity: float | None) -> float | None:
    """Return (total_assets - total_equity) / total_equity or None."""
    if total_equity is None:
        return None
    return safe_divide(total_assets - total_equity, total_equity)


def compute_pe_from_snapshot(
    pe_ratio: float | None,
    market_cap: float | None,
    net_income: float | None,
) -> tuple[float | None, str | None]:
    """
    Returns (pe_value, warning_or_None).

    Priority:
      1. snapshot pe_ratio if > 0
      2. market_cap / net_income only when net_income > 0
      3. otherwise None + warning
    """
    if pe_ratio is not None and pe_ratio > 0:
        return pe_ratio, None
    if market_cap is not None and net_income is not None and net_income > 0:
        calculated = safe_divide(market_cap, net_income)
        if calculated is not None:
            return calculated, None
    return None, "P/E hesaplanamadı: pe_ratio veya market_cap/net_income mevcut değil"


# ============================================================================
# Warning helpers
# ============================================================================


def _append_missing_field_warnings(
    symbol: str,
    income_statement: IncomeStatement,
    balance_sheet: BalanceSheet | None,
    warnings: list[str],
) -> None:
    """Collect non-fatal warnings for partial financial data."""
    if income_statement.revenue is None:
        warnings.append(f"{symbol}: revenue eksik")
    if income_statement.net_income is None:
        warnings.append(f"{symbol}: net_income eksik")
    if balance_sheet is None:
        warnings.append(f"{symbol}: balance_sheet eksik")
        return
    if balance_sheet.total_assets is None:
        warnings.append(f"{symbol}: total_assets eksik")
    if balance_sheet.total_equity is None:
        warnings.append(f"{symbol}: total_equity eksik")


# ============================================================================
# DB query helpers
# ============================================================================


async def get_latest_financials(
    db: AsyncSession,
    stock_id: int,
    period_type: PeriodType = PeriodType.ANNUAL,
) -> tuple[IncomeStatement | None, BalanceSheet | None]:
    """
    Return (income_statement, balance_sheet) for the latest period.
    Joins on stock_id + period_type, orders by statement_date DESC.
    """
    period_val = period_type.value

    inc_result = await db.execute(
        select(IncomeStatement)
        .where(IncomeStatement.stock_id == stock_id)
        .where(IncomeStatement.period_type == period_val)
        .order_by(IncomeStatement.statement_date.desc())
        .limit(1)
    )
    income_stmt = inc_result.scalar_one_or_none()

    if income_stmt is None:
        return None, None

    bs_result = await db.execute(
        select(BalanceSheet)
        .where(BalanceSheet.stock_id == stock_id)
        .where(BalanceSheet.period_type == period_val)
        .where(BalanceSheet.statement_date == income_stmt.statement_date)
        .limit(1)
    )
    balance_sheet = bs_result.scalar_one_or_none()

    return income_stmt, balance_sheet


async def get_previous_financials(
    db: AsyncSession,
    stock_id: int,
    period_type: PeriodType,
    current_date: date,
) -> tuple[IncomeStatement | None, BalanceSheet | None]:
    """
    Return (income_statement, balance_sheet) for the period immediately before current_date.
    """
    period_val = period_type.value

    inc_result = await db.execute(
        select(IncomeStatement)
        .where(IncomeStatement.stock_id == stock_id)
        .where(IncomeStatement.period_type == period_val)
        .where(IncomeStatement.statement_date < current_date)
        .order_by(IncomeStatement.statement_date.desc())
        .limit(1)
    )
    income_stmt = inc_result.scalar_one_or_none()

    if income_stmt is None:
        return None, None

    bs_result = await db.execute(
        select(BalanceSheet)
        .where(BalanceSheet.stock_id == stock_id)
        .where(BalanceSheet.period_type == period_val)
        .where(BalanceSheet.statement_date == income_stmt.statement_date)
        .limit(1)
    )
    balance_sheet = bs_result.scalar_one_or_none()

    return income_stmt, balance_sheet


async def get_financial_history(
    db: AsyncSession,
    stock_id: int,
    period_type: PeriodType = PeriodType.ANNUAL,
    limit: int = 4,
) -> list[IncomeStatement]:
    """
    Return income_statement rows ordered by statement_date DESC for chart time series.
    """
    period_val = period_type.value

    result = await db.execute(
        select(IncomeStatement)
        .where(IncomeStatement.stock_id == stock_id)
        .where(IncomeStatement.period_type == period_val)
        .order_by(IncomeStatement.statement_date.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


# ============================================================================
# CrewAI agent wrapper
# ============================================================================


def build_code_executor_agent() -> Any:
    """Build the CrewAI code executor role or fallback metadata."""
    settings = get_settings()
    return create_agent_or_spec(
        role="FinMatrix Code Executor",
        goal="Execute deterministic financial calculations for BIST stocks.",
        backstory="Expert in Turkish financial statement analysis.",
        llm_model=settings.query_understanding_model,
    )


@lru_cache(maxsize=1)
def get_code_executor_agent() -> Any:
    """Return the CrewAI code executor role lazily."""
    return build_code_executor_agent()


# ============================================================================
# Main entrypoint
# ============================================================================


async def run_numerical_analysis(
    db: AsyncSession,
    query: str,
    symbols: list[str],
    period_type: PeriodType = PeriodType.ANNUAL,
    needs_chart: bool = False,
    http_client: httpx.AsyncClient | None = None,
) -> NumericalAnalysisResult:
    """
    Run deterministic numerical analysis for the given symbols.

    Steps:
      1. Resolve each symbol → canonical → stock_id
      2. Fetch latest + previous financials for each symbol
      3. Fetch borsapy snapshot for P/E ratio
      4. Build FinancialMetricSnapshot list
      5. If multi-symbol: build ComparisonTableRow list
      6. If needs_chart: build ChartPayload from financial history
      7. Return NumericalAnalysisResult
    """
    _: tuple[str, Any] = (query, http_client)  # reserved for future use
    warnings: list[str] = []
    data_sources: list[str] = ["income_statements", "balance_sheets"]
    metrics: list[FinancialMetricSnapshot] = []
    all_stock_ids: dict[str, int] = {}
    snapshot_pe_by_symbol: dict[str, float | None] = {}

    # Step 1: symbol resolution
    for sym in symbols:
        canonical = await resolve_symbol(db, sym)
        if canonical is None:
            warnings.append(f"Sembol çözümlenemedi: {sym}")
            continue
        result = await db.execute(select(Stock.id).where(Stock.symbol == canonical))
        stock_id = result.scalar_one_or_none()
        if stock_id is None:
            warnings.append(f"Hisse bulunamadı: {sym}")
            continue
        all_stock_ids[canonical] = stock_id

    if not all_stock_ids:
        return NumericalAnalysisResult(
            symbols=symbols,
            metrics=[],
            comparison_table=None,
            chart=None,
            warnings=warnings,
            data_sources=data_sources,
            insufficient_data=True,
        )

    borsapy = BorsapyProvider()

    # Steps 2-4: fetch financials + snapshot for each resolved symbol
    for sym, stock_id in all_stock_ids.items():
        inc, bs = await get_latest_financials(db, stock_id, period_type)
        if inc is None:
            warnings.append(f"Finansal veri yok: {sym}")
            continue

        inc_prev, bs_prev = await get_previous_financials(
            db, stock_id, period_type, inc.statement_date
        )
        _ = bs_prev
        _append_missing_field_warnings(sym, inc, bs, warnings)

        # Try borsapy snapshot for P/E
        snapshot_pe: float | None = None
        snapshot_warning: str | None = None
        try:
            snapshot = borsapy.get_stock_snapshot(sym)
            snapshot_pe, snapshot_warning = compute_pe_from_snapshot(
                snapshot.pe_ratio, snapshot.market_cap, inc.net_income
            )
            if snapshot_warning:
                warnings.append(f"{sym}: {snapshot_warning}")
        except Exception as e:
            logger.warning(f"Borsapy snapshot failed for {sym}: {e}")
            warnings.append(f"{sym}: P/E için snapshot alınamadı ({e!s})")

        snapshot_pe_by_symbol[sym] = snapshot_pe

        # Build metric snapshot
        metrics.append(
            FinancialMetricSnapshot(
                symbol=sym,
                period_type=period_type,
                statement_date=inc.statement_date,
                revenue=inc.revenue,
                net_income=inc.net_income,
                total_assets=bs.total_assets if bs else None,
                total_equity=bs.total_equity if bs else None,
                net_profit_growth=net_profit_growth(
                    inc.net_income,
                    inc_prev.net_income if inc_prev else None,
                ),
                roe=roe(inc.net_income, bs.total_equity if bs else None),
                debt_to_equity=debt_to_equity(
                    bs.total_assets if bs else None,
                    bs.total_equity if bs else None,
                ),
                pe_ratio=snapshot_pe,
                source=inc.source,
            )
        )

    # Step 5: comparison table (multi-symbol only)
    comparison_table: list[ComparisonTableRow] | None = None
    if len(all_stock_ids) > 1:
        comparison_table = []
        symbols_list = list(all_stock_ids.keys())

        # Net Kar
        comparison_table.append(
            ComparisonTableRow(
                metric="Net Kar",
                values={
                    s: next(
                        (m.net_income for m in metrics if m.symbol == s), None
                    )
                    for s in symbols_list
                },
            )
        )
        # Hasılat
        comparison_table.append(
            ComparisonTableRow(
                metric="Hasılat",
                values={
                    s: next((m.revenue for m in metrics if m.symbol == s), None)
                    for s in symbols_list
                },
            )
        )
        # ROE
        comparison_table.append(
            ComparisonTableRow(
                metric="ROE",
                values={
                    s: next(
                        (
                            m.roe
                            for m in metrics
                            if m.symbol == s
                        ),
                        None,
                    )
                    for s in symbols_list
                },
            )
        )
        # P/E — use snapshot values already fetched
        comparison_table.append(
            ComparisonTableRow(
                metric="P/E",
                values={s: snapshot_pe_by_symbol.get(s) for s in symbols_list},
            )
        )
        # Debt/Equity
        comparison_table.append(
            ComparisonTableRow(
                metric="Debt/Equity",
                values={
                    s: next(
                        (
                            m.debt_to_equity
                            for m in metrics
                            if m.symbol == s
                        ),
                        None,
                    )
                    for s in symbols_list
                },
            )
        )

    # Step 6: chart payload
    chart: ChartPayload | None = None
    if needs_chart and all_stock_ids:
        # Build chart for first symbol (single-symbol at a time for now)
        primary_sym = list(all_stock_ids.keys())[0]
        primary_stock_id = all_stock_ids[primary_sym]
        history = await get_financial_history(db, primary_stock_id, period_type, limit=8)
        if history:
            series_data = [
                {"date": h.statement_date.isoformat(), "value": h.net_income}
                for h in reversed(history)
                if h.net_income is not None
            ]
            chart = ChartPayload(
                type="line",
                title=f"{primary_sym} Net Kar Trendi",
                series=[ChartSeries(name="Net Kar", data=series_data)],
            )

    insufficient_data = len(metrics) == 0

    return NumericalAnalysisResult(
        symbols=symbols,
        metrics=metrics,
        comparison_table=comparison_table,
        chart=chart,
        warnings=warnings,
        data_sources=data_sources,
        insufficient_data=insufficient_data,
    )
