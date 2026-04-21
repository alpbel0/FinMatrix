"""Unit tests for deterministic metric calculations."""

from datetime import date, datetime, timezone

import pytest

from app.models.stock import Stock
from app.models.stock_snapshot import StockSnapshotRecord
from app.services.analytics.metric_engine import (
    MetricEngine,
    compute_current_ratio,
    compute_debt_equity,
    compute_growth,
    compute_roa,
    compute_roe,
)
from tests.factories import create_financial_statement_set
from app.services.data.mappers.financials_mapper import (
    upsert_balance_sheet,
    upsert_income_statement,
)


class TestMetricFormulas:
    def test_formula_helpers_return_expected_values(self):
        assert compute_roe(25.0, 100.0) == 0.25
        assert compute_roa(20.0, 200.0) == 0.1
        assert compute_current_ratio(60.0, 40.0) == 1.5
        assert compute_debt_equity(75.0, 50.0) == 1.5
        assert compute_growth(120.0, 100.0) == 0.2

    def test_formula_helpers_handle_missing_and_zero_denominator(self):
        assert compute_roe(20.0, 0.0) is None
        assert compute_roa(None, 200.0) is None
        assert compute_current_ratio(60.0, None) is None
        assert compute_debt_equity(75.0, 0.0) is None
        assert compute_growth(120.0, 0.0) is None


class TestMetricEngine:
    @pytest.mark.asyncio
    async def test_compute_for_stock_calculates_all_internal_metrics(self, db_session):
        stock = Stock(symbol="THYAO", company_name="Turk Hava Yollari", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        latest = create_financial_statement_set(
            symbol="THYAO",
            statement_date=date(2024, 12, 31),
            total_assets=200.0,
            total_equity=100.0,
            total_liabilities=100.0,
            current_assets=80.0,
            current_liabilities=40.0,
            revenue=150.0,
            net_income=25.0,
        )
        previous = create_financial_statement_set(
            symbol="THYAO",
            statement_date=date(2023, 12, 31),
            total_assets=180.0,
            total_equity=90.0,
            total_liabilities=90.0,
            current_assets=70.0,
            current_liabilities=35.0,
            revenue=120.0,
            net_income=20.0,
        )

        await upsert_balance_sheet(db_session, "THYAO", latest)
        await upsert_income_statement(db_session, "THYAO", latest)
        await upsert_balance_sheet(db_session, "THYAO", previous)
        await upsert_income_statement(db_session, "THYAO", previous)

        engine = MetricEngine(db_session)
        result = await engine.compute_for_stock(stock.id, date(2026, 4, 21))

        assert result.values["roe"] == 0.25
        assert result.values["roa"] == 0.125
        assert result.values["current_ratio"] == 2.0
        assert result.values["debt_equity"] == 1.0
        assert result.values["revenue_growth"] == 0.25
        assert result.values["net_profit_growth"] == 0.25
        assert result.field_sources["roe"] == "calculated"
        assert result.warnings == []

    @pytest.mark.asyncio
    async def test_compute_for_stock_warns_on_period_mismatch(self, db_session):
        stock = Stock(symbol="GARAN", company_name="Garanti", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        income = create_financial_statement_set(
            symbol="GARAN",
            statement_date=date(2024, 12, 31),
            revenue=100.0,
            net_income=10.0,
        )
        balance = create_financial_statement_set(
            symbol="GARAN",
            statement_date=date(2023, 12, 31),
            total_assets=200.0,
            total_equity=80.0,
            total_liabilities=120.0,
            current_assets=70.0,
            current_liabilities=35.0,
        )

        await upsert_income_statement(db_session, "GARAN", income)
        await upsert_balance_sheet(db_session, "GARAN", balance)

        engine = MetricEngine(db_session)
        result = await engine.compute_for_stock(stock.id, date(2026, 4, 21))

        assert result.values["roe"] is None
        assert result.values["roa"] is None
        assert result.values["current_ratio"] is None
        assert result.values["debt_equity"] is None
        assert "do not align" in result.warnings[0]

    @pytest.mark.asyncio
    async def test_build_snapshot_payload_applies_precedence_and_historical_fallback(self, db_session):
        stock = Stock(symbol="AKBNK", company_name="Akbank", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        latest = create_financial_statement_set(
            symbol="AKBNK",
            statement_date=date(2024, 12, 31),
            total_assets=200.0,
            total_equity=100.0,
            total_liabilities=100.0,
            current_assets=None,
            current_liabilities=None,
            revenue=150.0,
            net_income=25.0,
        )
        previous = create_financial_statement_set(
            symbol="AKBNK",
            statement_date=date(2023, 12, 31),
            revenue=120.0,
            net_income=20.0,
        )
        await upsert_balance_sheet(db_session, "AKBNK", latest)
        await upsert_income_statement(db_session, "AKBNK", latest)
        await upsert_income_statement(db_session, "AKBNK", previous)

        db_session.add(
            StockSnapshotRecord(
                stock_id=stock.id,
                snapshot_date=date(2026, 4, 20),
                pb_ratio=1.15,
                current_ratio=1.6,
                source="provider:borsapy+historical_fallback:2026-04-19",
                field_sources={
                    "pb_ratio": "provider:borsapy",
                    "current_ratio": "historical_fallback:2026-04-19",
                },
                missing_fields_count=17,
                completeness_score=0.1053,
                is_partial=True,
                fetched_at=datetime.now(timezone.utc),
            )
        )
        await db_session.commit()

        provider_payload = {
            "pe_ratio": 4.5,
            "pb_ratio": None,
            "roe": 0.1,
            "roa": None,
            "current_ratio": None,
            "debt_equity": None,
            "revenue_growth": None,
            "net_profit_growth": None,
            "market_cap": 500.0,
            "last_price": 50.0,
            "daily_volume": 1000.0,
            "field_sources": {
                "pe_ratio": "provider:borsapy",
                "roe": "provider:borsapy",
                "market_cap": "provider:borsapy",
                "last_price": "provider:borsapy",
                "daily_volume": "provider:borsapy",
            },
            "fetched_at": datetime.now(timezone.utc),
        }

        engine = MetricEngine(db_session)
        payload = await engine.build_snapshot_payload(stock.id, date(2026, 4, 21), provider_payload)

        assert payload["roe"] == 0.25
        assert payload["field_sources"]["roe"] == "calculated"
        assert payload["pb_ratio"] == 1.15
        assert payload["field_sources"]["pb_ratio"] == "historical_fallback:2026-04-20"
        assert payload["current_ratio"] == 1.6
        assert payload["field_sources"]["current_ratio"] == "historical_fallback:2026-04-20"
        assert payload["source"].startswith("provider:borsapy")
