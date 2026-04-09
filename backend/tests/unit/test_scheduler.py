"""Unit tests for scheduler module."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.models.pipeline_log import PipelineLog
from app.services.pipeline.scheduler import (
    run_financials_weekly_job,
    run_kap_hourly_job,
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
    async def test_kap_hourly_logs_success_with_scheduler_job_name(self, db_session):
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
            await run_kap_hourly_job(run_id="test-kap-run")

        result = await db_session.execute(
            select(PipelineLog).where(PipelineLog.run_id == "test-kap-run")
        )
        log = result.scalar_one()

        assert log.pipeline_name == "kap_sync_hourly"
        assert log.status == "success"
        assert log.processed_count == 7
        assert log.details["job_name"] == "kap_sync_hourly"
        assert log.details["universe"] == "bist100"
