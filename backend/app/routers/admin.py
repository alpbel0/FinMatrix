"""Admin router for scheduler control and manual sync triggers."""

from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session
from app.models.scheduler_setting import SchedulerSetting
from app.models.pipeline_log import PipelineLog
from app.models.user import User
from app.schemas.scheduler import (
    FinancialReportingModeRequest,
    FinancialReportingModeResponse,
    ManualSyncRequest,
    ManualSyncResponse,
    SchedulerStatusResponse,
    JobStatus,
)
from app.services.auth_service import get_current_user
from app.services.pipeline.scheduler import (
    get_scheduler_status,
    run_price_sync_job,
    run_snapshot_sync_daily_job,
    run_financials_weekly_job,
    run_news_sync_hourly_job,
    run_news_sync_watchlist_job,
    run_news_sync_slow_job,
    run_report_sync_biweekly_job,
    run_kap_sync_job,
)
from app.services.pipeline.job_policy import get_symbols_by_universe
from app.services.utils.logging import logger


router = APIRouter(prefix="/api/admin", tags=["admin"])
security = HTTPBearer()


async def get_admin_user(
    db: AsyncSession = Depends(get_db_session),
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> User:
    """Dependency to get current user and verify admin status."""
    user = await get_current_user(db, credentials.credentials)
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


@router.get("/scheduler/status", response_model=SchedulerStatusResponse)
async def get_status(
    db: AsyncSession = Depends(get_db_session),
    admin_user: User = Depends(get_admin_user),
) -> SchedulerStatusResponse:
    """Get scheduler status including all job states and reporting mode."""
    # Get scheduler status
    scheduler_status = get_scheduler_status()

    # Get reporting mode
    setting = await db.get(SchedulerSetting, 1)
    if setting is None:
        setting = SchedulerSetting(id=1, financial_reporting_mode=False)
        db.add(setting)
        await db.commit()

    # Get last runs from pipeline_logs
    job_names = [
        "price_sync",
        "snapshot_sync_daily",
        "financials_sync_weekly",
        "financials_sync_reporting",
        "news_sync_hourly",
        "news_sync_watchlist",
        "news_sync_slow",
        "report_sync_biweekly",
        "pdf_download_hourly",
    ]

    jobs_status: dict[str, JobStatus] = {}
    for job_name in job_names:
        # Get last log for this job
        result = await db.execute(
            select(PipelineLog)
            .where(PipelineLog.pipeline_name == job_name)
            .order_by(PipelineLog.started_at.desc())
            .limit(1)
        )
        last_log = result.scalar_one_or_none()

        # Find job in scheduler
        job_info = None
        for job in scheduler_status.get("jobs", []):
            if job["id"] == job_name:
                job_info = job
                break

        jobs_status[job_name] = JobStatus(
            last_run=last_log.started_at if last_log else None,
            last_status=last_log.status if last_log else None,
            next_run=(
                datetime.fromisoformat(job_info["next_run"])
                if job_info and job_info.get("next_run")
                else None
            ),
        )

    return SchedulerStatusResponse(
        is_running=scheduler_status["is_running"],
        financial_reporting_mode=setting.financial_reporting_mode,
        financial_reporting_until=setting.financial_reporting_until,
        jobs=jobs_status,
    )


@router.post(
    "/scheduler/financial-reporting-mode",
    response_model=FinancialReportingModeResponse,
)
async def set_financial_reporting_mode(
    request: FinancialReportingModeRequest,
    db: AsyncSession = Depends(get_db_session),
    admin_user: User = Depends(get_admin_user),
) -> FinancialReportingModeResponse:
    """Enable or disable financial reporting mode.

    When enabled, financial sync runs every 4 hours for 7 days.
    """
    setting = await db.get(SchedulerSetting, 1)
    if setting is None:
        setting = SchedulerSetting(id=1)
        db.add(setting)

    if request.enabled:
        # Enable reporting mode for 7 days
        setting.financial_reporting_mode = True
        setting.financial_reporting_until = datetime.now(timezone.utc) + timedelta(days=7)
        setting.updated_by_user_id = admin_user.id
        logger.info(
            f"Financial reporting mode enabled by {admin_user.username} until "
            f"{setting.financial_reporting_until}"
        )
    else:
        # Disable reporting mode
        setting.financial_reporting_mode = False
        setting.financial_reporting_until = None
        setting.updated_by_user_id = admin_user.id
        logger.info(f"Financial reporting mode disabled by {admin_user.username}")

    await db.commit()

    return FinancialReportingModeResponse(
        financial_reporting_mode=setting.financial_reporting_mode,
        financial_reporting_until=setting.financial_reporting_until,
    )


@router.post("/scheduler/run/prices", response_model=ManualSyncResponse)
async def trigger_price_sync(
    db: AsyncSession = Depends(get_db_session),
    admin_user: User = Depends(get_admin_user),
) -> ManualSyncResponse:
    """Manually trigger a price sync job."""
    import uuid

    logger.info(f"Manual price sync triggered by {admin_user.username}")

    # Get symbols
    symbols = await get_symbols_by_universe(db, "all")

    # Run sync in background (fire and forget)
    # Note: In production, this should be queued to a background worker
    run_id = str(uuid.uuid4())

    # Trigger async job
    import asyncio

    asyncio.create_task(
        run_price_sync_job(symbols=symbols, trigger="manual", run_id=run_id)
    )

    return ManualSyncResponse(
        run_id=run_id,
        status="triggered",
        symbols_count=len(symbols),
        message="Price sync job triggered. Check pipeline_logs for results.",
    )


@router.post("/scheduler/run/financials", response_model=ManualSyncResponse)
async def trigger_financials_sync(
    db: AsyncSession = Depends(get_db_session),
    admin_user: User = Depends(get_admin_user),
) -> ManualSyncResponse:
    """Manually trigger a financial statements sync job."""
    import uuid

    logger.info(f"Manual financials sync triggered by {admin_user.username}")

    # Get symbols (BIST100 for financials)
    symbols = await get_symbols_by_universe(db, "bist100")

    run_id = str(uuid.uuid4())

    # Trigger async job
    import asyncio

    asyncio.create_task(
        run_financials_weekly_job(symbols=symbols, trigger="manual", run_id=run_id)
    )

    return ManualSyncResponse(
        run_id=run_id,
        status="triggered",
        symbols_count=len(symbols),
        message="Financials sync job triggered. Check pipeline_logs for results.",
    )


@router.post("/scheduler/run/snapshots", response_model=ManualSyncResponse)
async def trigger_snapshot_sync(
    request: ManualSyncRequest,
    db: AsyncSession = Depends(get_db_session),
    admin_user: User = Depends(get_admin_user),
) -> ManualSyncResponse:
    """Manually trigger a stock snapshot sync job."""
    import asyncio
    import uuid

    logger.info(
        "Manual snapshot sync triggered by %s for universe=%s",
        admin_user.username,
        request.universe,
    )

    symbols = await get_symbols_by_universe(db, request.universe)
    run_id = str(uuid.uuid4())
    asyncio.create_task(
        run_snapshot_sync_daily_job(symbols=symbols, trigger="manual", run_id=run_id)
    )

    return ManualSyncResponse(
        run_id=run_id,
        status="triggered",
        symbols_count=len(symbols),
        message="Snapshot sync job triggered. Check pipeline_logs for results.",
    )


@router.post("/scheduler/run/kap", response_model=ManualSyncResponse)
async def trigger_kap_sync(
    request: ManualSyncRequest,
    db: AsyncSession = Depends(get_db_session),
    admin_user: User = Depends(get_admin_user),
) -> ManualSyncResponse:
    """Manually trigger a KAP sync job.

    Args:
        request: Universe to sync - "all", "bist100", "watchlist"
    """
    import uuid

    logger.info(
        f"Manual KAP sync triggered by {admin_user.username} for universe={request.universe}"
    )

    # Get symbols
    symbols = await get_symbols_by_universe(db, request.universe)

    run_id = str(uuid.uuid4())

    # Trigger async job
    import asyncio

    if request.universe == "bist100":
        task = run_news_sync_hourly_job(symbols=symbols, trigger="manual", run_id=run_id)
    elif request.universe == "watchlist":
        task = run_news_sync_watchlist_job(symbols=symbols, trigger="manual", run_id=run_id)
    elif request.universe == "slow":
        task = run_news_sync_slow_job(symbols=symbols, trigger="manual", run_id=run_id)
    else:
        task = run_kap_sync_job(
            job_name="news_sync_manual",
            symbols=symbols,
            trigger="manual",
            run_id=run_id,
            universe=request.universe,
            filing_types=["ODA", "DG"],
            days_back=3,
        )

    asyncio.create_task(task)

    return ManualSyncResponse(
        run_id=run_id,
        status="triggered",
        symbols_count=len(symbols),
        message=f"KAP sync job triggered for {request.universe}. Check pipeline_logs for results.",
    )
