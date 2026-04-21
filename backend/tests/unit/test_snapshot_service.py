"""Unit tests for stock snapshot service helpers."""

from datetime import date
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.models.pipeline_log import PipelineLog
from app.models.stock import Stock
from app.models.stock_snapshot import StockSnapshotRecord
from app.models.sync_job_run import SyncJobRun
from app.services.data.providers.snapshot_provider import RawSnapshotPayload
from app.services.snapshot_service import (
    _FetchedSnapshot,
    _build_freshness,
    sync_all_active_stock_snapshots,
    sync_one_stock_snapshot,
)
from app.services.data.mappers.financials_mapper import (
    upsert_balance_sheet,
    upsert_income_statement,
)
from tests.factories import create_financial_statement_set


class TestSnapshotFreshness:
    def test_build_freshness_marks_missing_snapshot_as_stale(self):
        freshness = _build_freshness(None)

        assert freshness["is_stale"] is True
        assert freshness["stale_reason"] == "no_snapshot"

    def test_build_freshness_for_past_snapshot_returns_reason(self):
        freshness = _build_freshness(date(2026, 4, 20))

        assert freshness["is_stale"] is True
        assert freshness["stale_reason"] in {"market_closed", "awaiting_daily_sync", "sync_delayed"}


class TestSnapshotSyncFlows:
    @pytest.mark.asyncio
    async def test_sync_one_stock_snapshot_upserts_snapshot_with_calculated_sources(self, db_session):
        stock = Stock(symbol="THYAO", company_name="Turk Hava Yollari", sector="Transportation", is_active=True)
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
            revenue=120.0,
            net_income=20.0,
        )
        await upsert_balance_sheet(db_session, "THYAO", latest)
        await upsert_income_statement(db_session, "THYAO", latest)
        await upsert_income_statement(db_session, "THYAO", previous)

        fetched_snapshot = _FetchedSnapshot(
            symbol="THYAO",
            stock_id=stock.id,
            primary_snapshot=RawSnapshotPayload(
                symbol="THYAO",
                provider="borsapy",
                sections={
                    "fast_info": {
                        "pe_ratio": 5.8,
                        "pb_ratio": 1.4,
                        "market_cap": 100_000_000,
                        "last_price": 255.4,
                        "volume": 150000,
                    },
                    "info": {"roe": 0.11},
                },
            ),
        )

        with patch("app.services.snapshot_service._fetch_provider_snapshot", AsyncMock(return_value=fetched_snapshot)):
            result = await sync_one_stock_snapshot(db_session, stock.id, snapshot_date=date(2026, 4, 21))

        assert result.success is True
        assert result.symbol == "THYAO"

        saved = await db_session.get(StockSnapshotRecord, (stock.id, date(2026, 4, 21)))
        assert saved is not None
        assert saved.pe_ratio == 5.8
        assert saved.pb_ratio == 1.4
        assert saved.roe == 0.25
        assert saved.roa == 0.125
        assert saved.current_ratio == 2.0
        assert saved.debt_equity == 1.0
        assert saved.revenue_growth == 0.25
        assert saved.field_sources["roe"] == "calculated"
        assert saved.field_sources["pe_ratio"] == "provider:borsapy"

    @pytest.mark.asyncio
    async def test_sync_all_active_stock_snapshots_creates_summary_and_isolates_failures(self, db_session):
        stocks = [
            Stock(symbol="AKBNK", company_name="Akbank", sector="Finance", is_active=True),
            Stock(symbol="GARAN", company_name="Garanti", sector="Finance", is_active=True),
            Stock(symbol="THYAO", company_name="Turk Hava Yollari", sector="Transportation", is_active=True),
            Stock(symbol="INACTIVE", company_name="Inactive", sector="Test", is_active=False),
        ]
        db_session.add_all(stocks)
        await db_session.commit()

        active_by_symbol = {stock.symbol: stock for stock in stocks if stock.is_active}
        fetched_items = [
            _FetchedSnapshot(
                symbol="AKBNK",
                stock_id=active_by_symbol["AKBNK"].id,
                primary_snapshot=RawSnapshotPayload(
                    symbol="AKBNK",
                    provider="borsapy",
                    sections={"fast_info": {"pe_ratio": 4.2, "pb_ratio": 1.1, "market_cap": 200.0, "last_price": 50.0, "volume": 1000.0}},
                ),
            ),
            _FetchedSnapshot(
                symbol="GARAN",
                stock_id=active_by_symbol["GARAN"].id,
                primary_snapshot=RawSnapshotPayload(
                    symbol="GARAN",
                    provider="borsapy",
                    sections={"fast_info": {"pe_ratio": 5.1, "market_cap": 300.0, "last_price": 75.0}},
                ),
            ),
            _FetchedSnapshot(
                symbol="THYAO",
                stock_id=active_by_symbol["THYAO"].id,
                error_message="provider timeout",
            ),
        ]

        with patch("app.services.snapshot_service._fetch_snapshot_chunk", AsyncMock(return_value=fetched_items)):
            result = await sync_all_active_stock_snapshots(
                db_session,
                snapshot_date=date(2026, 4, 21),
                run_id="snapshot-run-1",
                trigger="manual",
            )

        assert result.status == "partial"
        assert result.successful == []
        assert result.partial == ["AKBNK", "GARAN"]
        assert len(result.failed) == 1
        assert result.failed[0].symbol == "THYAO"

        job_run = (
            await db_session.execute(
                select(SyncJobRun).where(SyncJobRun.job_name == "snapshot_sync_daily")
            )
        ).scalar_one()
        assert job_run.total_stocks == 3
        assert job_run.success_count == 0
        assert job_run.partial_count == 2
        assert job_run.failed_count == 1
        assert job_run.status == "partial"

        pipeline_log = (
            await db_session.execute(
                select(PipelineLog).where(PipelineLog.run_id == "snapshot-run-1")
            )
        ).scalar_one()
        assert pipeline_log.status == "partial"
        assert pipeline_log.processed_count == 2
