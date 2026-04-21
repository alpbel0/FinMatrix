"""Unit tests for scheduler module."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.models.pipeline_log import PipelineLog
from app.services.pipeline.scheduler import (
    start_scheduler,
    run_financials_weekly_job,
    run_news_sync_hourly_job,
    run_report_sync_biweekly_job,
)


class _SessionFactory:
    """Wrap an existing async session for async-with usage."""

    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, exc_type, exc, tb):
        return False


def _wrap_session(session):
    return _SessionFactory(session)


class TestSchedulerLogging:
    """Tests that scheduler wrappers write job-level success logs."""

    @pytest.mark.asyncio
    async def test_financials_weekly_logs_success_with_scheduler_job_name(self, db_session):
        fake_result = SimpleNamespace(
            status="success",
            total_statements=12,
            finished_at=datetime.now(timezone.utc),
        )

        with (
            patch("app.services.pipeline.scheduler.AsyncSessionLocal", lambda: _wrap_session(db_session)),
            patch(
                "app.services.pipeline.scheduler.get_bist100_symbols_from_provider",
                AsyncMock(return_value=["THYAO", "GARAN"]),
            ),
            patch(
                "app.services.pipeline.scheduler.batch_sync_financials",
                AsyncMock(return_value=fake_result),
            ),
        ):
            await run_financials_weekly_job(run_id="test-financial-run")

        result = await db_session.execute(
            select(PipelineLog).where(PipelineLog.run_id == "test-financial-run")
        )
        log = result.scalar_one()

        assert log.pipeline_name == "financials_sync_weekly"
        assert log.status == "success"
        assert log.processed_count == 12
        assert log.details["job_name"] == "financials_sync_weekly"
        assert log.details["trigger"] == "scheduled"

    @pytest.mark.asyncio
    async def test_news_hourly_logs_success_with_scheduler_job_name(self, db_session):
        fake_result = SimpleNamespace(
            status="success",
            total_processed=7,
            finished_at=datetime.now(timezone.utc),
        )

        with (
            patch("app.services.pipeline.scheduler.AsyncSessionLocal", lambda: _wrap_session(db_session)),
            patch(
                "app.services.pipeline.scheduler.get_bist100_symbols_from_provider",
                AsyncMock(return_value=["THYAO"]),
            ),
            patch(
                "app.services.pipeline.scheduler.batch_sync_kap_filings",
                AsyncMock(return_value=fake_result),
            ),
        ):
            await run_news_sync_hourly_job(run_id="test-news-run")

        result = await db_session.execute(
            select(PipelineLog).where(PipelineLog.run_id == "test-news-run")
        )
        log = result.scalar_one()

        assert log.pipeline_name == "news_sync_hourly"
        assert log.status == "success"
        assert log.processed_count == 7
        assert log.details["job_name"] == "news_sync_hourly"
        assert log.details["universe"] == "bist100"
        assert log.details["filing_types"] == ["ODA", "DG"]

    @pytest.mark.asyncio
    async def test_report_biweekly_logs_success_with_report_job_name(self, db_session):
        fake_result = SimpleNamespace(
            status="success",
            total_processed=5,
            finished_at=datetime.now(timezone.utc),
        )

        with (
            patch("app.services.pipeline.scheduler.AsyncSessionLocal", lambda: _wrap_session(db_session)),
            patch(
                "app.services.pipeline.scheduler.get_all_active_symbols",
                AsyncMock(return_value=["THYAO", "GARAN"]),
            ),
            patch(
                "app.services.pipeline.scheduler.batch_sync_kap_filings",
                AsyncMock(return_value=fake_result),
            ),
        ):
            await run_report_sync_biweekly_job(run_id="test-report-run")

        result = await db_session.execute(
            select(PipelineLog).where(PipelineLog.run_id == "test-report-run")
        )
        log = result.scalar_one()

        assert log.pipeline_name == "report_sync_biweekly"
        assert log.status == "success"
        assert log.processed_count == 5
        assert log.details["job_name"] == "report_sync_biweekly"
        assert log.details["universe"] == "all_active"
        assert log.details["filing_types"] == ["FR", "FAR"]


class TestSchedulerRegistration:
    @pytest.mark.asyncio
    async def test_start_scheduler_registers_new_news_and_report_jobs(self):
        fake_jobs = [
            SimpleNamespace(id="price_sync"),
            SimpleNamespace(id="news_sync_hourly"),
            SimpleNamespace(id="news_sync_watchlist"),
            SimpleNamespace(id="news_sync_slow"),
            SimpleNamespace(id="report_sync_biweekly"),
            SimpleNamespace(id="pdf_download_hourly"),
        ]
        fake_settings = SimpleNamespace(
            news_sync_hourly_enabled=True,
            news_sync_watchlist_hour=21,
            news_sync_slow_interval_days=3,
            news_sync_slow_hour=2,
            report_sync_interval_days=14,
            report_sync_window_start_hour=3,
            report_sync_window_end_hour=5,
            pdf_download_hourly_enabled=True,
        )

        with (
            patch("app.services.pipeline.scheduler.get_settings", return_value=fake_settings),
            patch("app.services.pipeline.scheduler.scheduler.add_job") as mock_add_job,
            patch("app.services.pipeline.scheduler.scheduler.start") as mock_start,
            patch("app.services.pipeline.scheduler.scheduler.get_jobs", return_value=fake_jobs),
        ):
            await start_scheduler()

        registered_ids = [call.kwargs["id"] for call in mock_add_job.call_args_list]
        assert "news_sync_hourly" in registered_ids
        assert "news_sync_watchlist" in registered_ids
        assert "news_sync_slow" in registered_ids
        assert "report_sync_biweekly" in registered_ids
        assert "pdf_download_hourly" in registered_ids
        mock_start.assert_called_once()
