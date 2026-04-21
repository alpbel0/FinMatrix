"""Integration tests for admin scheduler API."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.main import app
from app.models.pipeline_log import PipelineLog
from app.models.scheduler_setting import SchedulerSetting
from app.models.user import User
from app.routers.admin import get_admin_user


@pytest.fixture
def admin_user() -> User:
    return User(
        id=999,
        username="admin",
        email="admin@test.com",
        password_hash="hash",
        is_admin=True,
    )


@pytest.fixture
def override_admin(admin_user):
    async def _override():
        return admin_user

    app.dependency_overrides[get_admin_user] = _override
    yield
    app.dependency_overrides.pop(get_admin_user, None)


class TestAdminSchedulerApi:
    @pytest.mark.asyncio
    async def test_manual_kap_trigger_uses_watchlist_job(self, client, db_session, override_admin):
        with (
            patch(
                "app.routers.admin.get_symbols_by_universe",
                AsyncMock(return_value=["THYAO", "GARAN"]),
            ),
            patch(
                "app.routers.admin.run_news_sync_watchlist_job",
                AsyncMock(return_value=None),
            ) as mock_watchlist_job,
        ):
            response = await client.post(
                "/api/admin/scheduler/run/kap",
                headers={"Authorization": "Bearer test-token"},
                json={"universe": "watchlist"},
            )

            await asyncio.sleep(0)

        assert response.status_code == 200
        payload = response.json()
        assert payload["symbols_count"] == 2
        mock_watchlist_job.assert_awaited_once()
        assert mock_watchlist_job.await_args.kwargs["symbols"] == ["THYAO", "GARAN"]
        assert mock_watchlist_job.await_args.kwargs["trigger"] == "manual"
        assert mock_watchlist_job.await_args.kwargs["run_id"] == payload["run_id"]

    @pytest.mark.asyncio
    async def test_manual_price_trigger_passes_manual_run_id_and_symbols(self, client, db_session, override_admin):
        with (
            patch(
                "app.routers.admin.get_symbols_by_universe",
                AsyncMock(return_value=["THYAO", "GARAN", "ASELS"]),
            ),
            patch(
                "app.routers.admin.run_price_sync_job",
                AsyncMock(return_value=None),
            ) as mock_price_job,
        ):
            response = await client.post(
                "/api/admin/scheduler/run/prices",
                headers={"Authorization": "Bearer test-token"},
            )

            await asyncio.sleep(0)

        assert response.status_code == 200
        payload = response.json()
        assert payload["symbols_count"] == 3
        mock_price_job.assert_awaited_once()
        assert mock_price_job.await_args.kwargs["symbols"] == ["THYAO", "GARAN", "ASELS"]
        assert mock_price_job.await_args.kwargs["trigger"] == "manual"
        assert mock_price_job.await_args.kwargs["run_id"] == payload["run_id"]

    @pytest.mark.asyncio
    async def test_manual_snapshot_trigger_passes_manual_run_id_and_symbols(self, client, db_session, override_admin):
        with (
            patch(
                "app.routers.admin.get_symbols_by_universe",
                AsyncMock(return_value=["THYAO", "GARAN"]),
            ),
            patch(
                "app.routers.admin.run_snapshot_sync_daily_job",
                AsyncMock(return_value=None),
            ) as mock_snapshot_job,
        ):
            response = await client.post(
                "/api/admin/scheduler/run/snapshots",
                headers={"Authorization": "Bearer test-token"},
                json={"universe": "all"},
            )

            await asyncio.sleep(0)

        assert response.status_code == 200
        payload = response.json()
        assert payload["symbols_count"] == 2
        mock_snapshot_job.assert_awaited_once()
        assert mock_snapshot_job.await_args.kwargs["symbols"] == ["THYAO", "GARAN"]
        assert mock_snapshot_job.await_args.kwargs["trigger"] == "manual"
        assert mock_snapshot_job.await_args.kwargs["run_id"] == payload["run_id"]

    @pytest.mark.asyncio
    async def test_scheduler_status_reads_scheduler_job_logs(self, client, db_session, override_admin):
        setting = SchedulerSetting(
            id=1,
            financial_reporting_mode=True,
            financial_reporting_until=datetime.now(timezone.utc),
        )
        db_session.add(setting)
        db_session.add(
            PipelineLog(
                run_id="run-1",
                pipeline_name="financials_sync_weekly",
                status="success",
                started_at=datetime(2026, 4, 8, 8, 0, tzinfo=timezone.utc),
                finished_at=datetime(2026, 4, 8, 8, 5, tzinfo=timezone.utc),
                processed_count=10,
                details={"job_name": "financials_sync_weekly"},
            )
        )
        await db_session.commit()

        with patch(
            "app.routers.admin.get_scheduler_status",
            return_value={
                "is_running": True,
                "jobs": [
                    {
                        "id": "financials_sync_weekly",
                        "name": "Financials Sync Weekly",
                        "next_run": "2026-04-15T06:00:00+03:00",
                    }
                ],
            },
        ):
            response = await client.get(
                "/api/admin/scheduler/status",
                headers={"Authorization": "Bearer test-token"},
            )

        assert response.status_code == 200
        payload = response.json()
        assert payload["is_running"] is True
        assert payload["financial_reporting_mode"] is True
        assert payload["jobs"]["financials_sync_weekly"]["last_status"] == "success"
        assert payload["jobs"]["financials_sync_weekly"]["last_run"] is not None
        assert payload["jobs"]["financials_sync_weekly"]["next_run"] is not None
