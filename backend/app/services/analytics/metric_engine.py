"""Deterministic metric calculation and snapshot precedence resolution."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.balance_sheet import BalanceSheet
from app.models.income_statement import IncomeStatement
from app.models.stock_snapshot import StockSnapshotRecord
from app.services.data.mappers.snapshot_normalizer import (
    SNAPSHOT_FIELDS,
    finalize_snapshot_payload,
)
from app.services.data.mappers.stock_snapshot_mapper import get_latest_snapshot_before_date


CALCULATED_SOURCE = "calculated"
FALLBACK_PREFIX = "historical_fallback"


@dataclass(slots=True)
class MetricEngineResult:
    values: dict[str, float | None]
    field_sources: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    as_of_date: date | None = None
    used_historical_fallback: list[str] = field(default_factory=list)


class MetricEngine:
    """Compute financial metrics from persisted statements and merge source precedence."""

    def __init__(self, db: AsyncSession):
        self._db = db

    async def compute_for_stock(self, stock_id: int, snapshot_date: date) -> MetricEngineResult:
        incomes = await self._get_annual_incomes(stock_id)
        balances = await self._get_annual_balances(stock_id)

        latest_income, latest_balance = self._find_matching_period(incomes, balances)
        previous_income = self._find_previous_income(incomes, latest_income)

        values: dict[str, float | None] = {
            "roe": None,
            "roa": None,
            "current_ratio": None,
            "debt_equity": None,
            "revenue_growth": None,
            "net_profit_growth": None,
        }
        field_sources: dict[str, str] = {}
        warnings: list[str] = []

        if latest_income and latest_balance:
            if latest_income.statement_date != latest_balance.statement_date:
                warnings.append(
                    "income statement and balance sheet dates do not align; profitability metrics skipped"
                )
            else:
                self._assign_value(values, field_sources, "roe", compute_roe(latest_income.net_income, latest_balance.total_equity))
                self._assign_value(values, field_sources, "roa", compute_roa(latest_income.net_income, latest_balance.total_assets))
                self._assign_value(
                    values,
                    field_sources,
                    "current_ratio",
                    compute_current_ratio(latest_balance.current_assets, latest_balance.current_liabilities),
                )
                self._assign_value(
                    values,
                    field_sources,
                    "debt_equity",
                    compute_debt_equity(latest_balance.total_liabilities, latest_balance.total_equity),
                )
                if latest_balance.total_equity is not None and latest_balance.total_equity < 0:
                    warnings.append("negative equity detected for latest annual statement")

        if latest_income and previous_income:
            self._assign_value(
                values,
                field_sources,
                "revenue_growth",
                compute_growth(latest_income.revenue, previous_income.revenue),
            )
            self._assign_value(
                values,
                field_sources,
                "net_profit_growth",
                compute_growth(latest_income.net_income, previous_income.net_income),
            )

        return MetricEngineResult(
            values=values,
            field_sources=field_sources,
            warnings=warnings,
            as_of_date=latest_income.statement_date if latest_income else None,
        )

    async def build_snapshot_payload(
        self,
        stock_id: int,
        snapshot_date: date,
        provider_payload: dict[str, Any],
    ) -> dict[str, Any]:
        computed = await self.compute_for_stock(stock_id, snapshot_date)
        fallback_snapshot = await get_latest_snapshot_before_date(self._db, stock_id, snapshot_date)

        payload = {field: provider_payload.get(field) for field in SNAPSHOT_FIELDS}
        field_sources = dict(provider_payload.get("field_sources") or {})

        for field, value in computed.values.items():
            if value is not None:
                payload[field] = value
                field_sources[field] = computed.field_sources[field]

        if fallback_snapshot is not None:
            for field in SNAPSHOT_FIELDS:
                if payload.get(field) is None:
                    fallback_value = getattr(fallback_snapshot, field, None)
                    if fallback_value is None:
                        continue
                    payload[field] = fallback_value
                    field_sources[field] = f"{FALLBACK_PREFIX}:{fallback_snapshot.snapshot_date.isoformat()}"
                    computed.used_historical_fallback.append(field)

        payload["fetched_at"] = provider_payload.get("fetched_at")
        payload = finalize_snapshot_payload(payload, field_sources)
        payload["warnings"] = computed.warnings
        payload["calculation_as_of_date"] = computed.as_of_date
        return payload

    async def _get_annual_incomes(self, stock_id: int) -> list[IncomeStatement]:
        result = await self._db.execute(
            select(IncomeStatement)
            .where(IncomeStatement.stock_id == stock_id)
            .where(IncomeStatement.period_type == "annual")
            .order_by(IncomeStatement.statement_date.desc())
        )
        return list(result.scalars().all())

    async def _get_annual_balances(self, stock_id: int) -> list[BalanceSheet]:
        result = await self._db.execute(
            select(BalanceSheet)
            .where(BalanceSheet.stock_id == stock_id)
            .where(BalanceSheet.period_type == "annual")
            .order_by(BalanceSheet.statement_date.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    def _find_matching_period(
        incomes: list[IncomeStatement],
        balances: list[BalanceSheet],
    ) -> tuple[IncomeStatement | None, BalanceSheet | None]:
        balances_by_date = {balance.statement_date: balance for balance in balances}
        for income in incomes:
            balance = balances_by_date.get(income.statement_date)
            if balance is not None:
                return income, balance
        return (incomes[0], balances[0]) if incomes and balances else (None, None)

    @staticmethod
    def _find_previous_income(
        incomes: list[IncomeStatement],
        latest_income: IncomeStatement | None,
    ) -> IncomeStatement | None:
        if latest_income is None:
            return None
        for income in incomes:
            if income.statement_date < latest_income.statement_date:
                return income
        return None

    @staticmethod
    def _assign_value(
        values: dict[str, float | None],
        field_sources: dict[str, str],
        field_name: str,
        value: float | None,
    ) -> None:
        values[field_name] = value
        if value is not None:
            field_sources[field_name] = CALCULATED_SOURCE


def compute_roe(net_income: float | None, total_equity: float | None) -> float | None:
    return _safe_divide(net_income, total_equity)


def compute_roa(net_income: float | None, total_assets: float | None) -> float | None:
    return _safe_divide(net_income, total_assets)


def compute_current_ratio(current_assets: float | None, current_liabilities: float | None) -> float | None:
    return _safe_divide(current_assets, current_liabilities)


def compute_debt_equity(total_liabilities: float | None, total_equity: float | None) -> float | None:
    return _safe_divide(total_liabilities, total_equity)


def compute_growth(latest_value: float | None, previous_value: float | None) -> float | None:
    if latest_value is None or previous_value in (None, 0):
        return None
    return (latest_value - previous_value) / abs(previous_value)


def _safe_divide(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator
