"""Scheduler module for scheduled sync jobs.

This module provides APScheduler-based scheduling for:
- Price sync: Every 15 minutes during BIST trading hours
- Financial sync: Weekly (normal) + 4-hourly (reporting mode)
- News sync: Hourly (BIST100), Daily (watchlist), 3-day (slow)
- Report sync: Bi-weekly for FR/FAR disclosures
- PDF download: Hourly
- Chunking: Hourly (process downloaded PDFs)
- Embedding: Every 10 minutes (embed pending chunks)
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models.scheduler_setting import SchedulerSetting
from app.models.pipeline_log import PipelineLog
from app.services.data.market_data_service import batch_sync_prices
from app.services.financials_service import batch_sync_financials
from app.services.snapshot_service import sync_all_active_stock_snapshots
from app.services.data.kap_data_service import batch_sync_kap_filings
from app.services.data.pdf_download_service import (
    batch_download_pending_pdfs,
    batch_retry_failed_downloads,
)
from app.services.pipeline.chunking_service import batch_chunk_completed_pdfs
from app.services.pipeline.embedding_service import batch_embed_pending_chunks
from app.services.pipeline.market_hours import is_bist_trading_hours
from app.services.pipeline.job_policy import (
    get_all_active_symbols,
    get_bist100_symbols_from_provider,
    get_non_priority_active_symbols,
    get_watchlist_symbols,
)
from app.services.utils.logging import logger


# ============================================================================
# Scheduler Instance
# ============================================================================

scheduler = AsyncIOScheduler(timezone="Europe/Istanbul")


# ============================================================================
# Pipeline Log Helper
# ============================================================================


async def _log_job_execution(
    db: AsyncSession,
    job_name: str,
    run_id: str,
    status: str,
    started_at: datetime,
    finished_at: datetime | None = None,
    processed_count: int = 0,
    error_message: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Create or update a pipeline log entry."""
    log = PipelineLog(
        run_id=run_id,
        pipeline_name=job_name,
        status=status,
        started_at=started_at,
        finished_at=finished_at,
        processed_count=processed_count,
        error_message=error_message[:500] if error_message else None,
        details=details or {},
    )
    db.add(log)
    await db.commit()


async def _log_skipped_job(
    db: AsyncSession,
    job_name: str,
    reason: str,
    trigger: str = "scheduled",
    run_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Log a skipped job execution."""
    run_id = run_id or str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    job_details = {"job_name": job_name, "trigger": trigger, "skipped_reason": reason}
    if details:
        job_details.update(details)

    await _log_job_execution(
        db=db,
        job_name=job_name,
        run_id=run_id,
        status="skipped",
        started_at=now,
        finished_at=now,
        processed_count=0,
        details=job_details,
    )


# ============================================================================
# Scheduler Setting Helper
# ============================================================================


async def _get_scheduler_setting(db: AsyncSession) -> SchedulerSetting:
    """Get or create scheduler setting."""
    setting = await db.get(SchedulerSetting, 1)
    if setting is None:
        # Create default setting
        setting = SchedulerSetting(
            id=1,
            financial_reporting_mode=False,
            financial_reporting_until=None,
        )
        db.add(setting)
        await db.commit()
    return setting


async def _check_reporting_mode(db: AsyncSession) -> bool:
    """Check if reporting mode is active, auto-disable if expired."""
    setting = await _get_scheduler_setting(db)

    if setting.financial_reporting_mode:
        # Check if expired
        if setting.financial_reporting_until:
            if setting.financial_reporting_until < datetime.now(timezone.utc):
                # Auto-disable expired reporting mode
                logger.info("Reporting mode expired, auto-disabling")
                setting.financial_reporting_mode = False
                setting.financial_reporting_until = None
                await db.commit()
                return False
        return True
    return False


def _price_success_details(symbols: list[str], trigger: str) -> dict[str, Any]:
    return {
        "job_name": "price_sync",
        "trigger": trigger,
        "universe": "custom" if trigger == "manual" else "all_active",
        "symbol_count": len(symbols),
        "market_open": True,
        "reporting_mode": False,
    }


def _financial_success_details(job_name: str, symbols: list[str], trigger: str, reporting_mode: bool) -> dict[str, Any]:
    return {
        "job_name": job_name,
        "trigger": trigger,
        "universe": "custom" if trigger == "manual" else "bist100",
        "symbol_count": len(symbols),
        "reporting_mode": reporting_mode,
    }


def _kap_success_details(job_name: str, symbols: list[str], trigger: str, universe: str, filing_types: list[str], days_back: int) -> dict[str, Any]:
    return {
        "job_name": job_name,
        "trigger": trigger,
        "universe": universe,
        "pipeline_type": "report" if any(ft in {"FR", "FAR"} for ft in filing_types) else "news",
        "symbol_count": len(symbols),
        "filing_types": filing_types,
        "days_back": days_back,
    }


def _build_report_sync_trigger() -> IntervalTrigger:
    """Build the bi-weekly report trigger anchored to the configured night window."""
    settings = get_settings()
    start_hour = settings.report_sync_window_start_hour
    end_hour = settings.report_sync_window_end_hour
    report_hour = start_hour if start_hour <= end_hour else end_hour

    now = datetime.now(scheduler.timezone)
    start_date = now.replace(hour=report_hour, minute=0, second=0, microsecond=0)
    if start_date <= now:
        start_date = start_date + timedelta(days=1)

    return IntervalTrigger(
        days=settings.report_sync_interval_days,
        start_date=start_date,
        timezone="Europe/Istanbul",
    )


# ============================================================================
# Job Execution Wrappers
# ============================================================================


async def run_price_sync_job(
    *,
    symbols: list[str] | None = None,
    trigger: str = "scheduled",
    run_id: str | None = None,
) -> None:
    """Execute price sync job with market hours check."""
    job_name = "price_sync"
    run_id = run_id or str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as db:
        try:
            # Check market hours
            if trigger == "scheduled" and not is_bist_trading_hours():
                logger.info(f"{job_name}: Market closed, skipping")
                await _log_skipped_job(db, job_name, "market_closed", trigger=trigger, run_id=run_id)
                return

            # Get universe
            symbols = symbols or await get_all_active_symbols(db)
            logger.info(f"{job_name}: Syncing {len(symbols)} symbols")

            # Execute sync
            result = await batch_sync_prices(db, symbols, period="1d")

            await _log_job_execution(
                db=db,
                job_name=job_name,
                run_id=run_id,
                status=result.status,
                started_at=started_at,
                finished_at=result.finished_at,
                processed_count=result.total_processed,
                details=_price_success_details(symbols, trigger),
            )

            logger.info(
                f"{job_name}: Completed - status={result.status}, "
                f"processed={result.total_processed}"
            )

        except Exception as e:
            logger.exception(f"{job_name}: Failed with error")
            await _log_job_execution(
                db=db,
                job_name=job_name,
                run_id=run_id,
                status="failed",
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
                error_message=str(e),
                details={"trigger": trigger, "job_name": job_name},
            )


async def run_snapshot_sync_daily_job(
    *,
    symbols: list[str] | None = None,
    trigger: str = "scheduled",
    run_id: str | None = None,
) -> None:
    """Execute daily stock snapshot sync job."""
    run_id = run_id or str(uuid.uuid4())

    async with AsyncSessionLocal() as db:
        try:
            if symbols is not None:
                logger.info("snapshot_sync_daily: Syncing %s symbols", len(symbols))
                from app.services.snapshot_service import batch_sync_stock_snapshots

                await batch_sync_stock_snapshots(
                    db,
                    symbols,
                    run_id=run_id,
                    trigger=trigger,
                )
            else:
                logger.info("snapshot_sync_daily: Syncing all active symbols")
                await sync_all_active_stock_snapshots(
                    db,
                    run_id=run_id,
                    trigger=trigger,
                )
        except Exception:
            logger.exception("snapshot_sync_daily: Failed with error")


async def run_financials_weekly_job(
    *,
    symbols: list[str] | None = None,
    trigger: str = "scheduled",
    run_id: str | None = None,
) -> None:
    """Execute weekly financial sync job."""
    job_name = "financials_sync_weekly"
    run_id = run_id or str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as db:
        try:
            # Get universe (BIST100)
            symbols = symbols or await get_bist100_symbols_from_provider()
            logger.info(f"{job_name}: Syncing {len(symbols)} symbols")

            # Execute sync
            result = await batch_sync_financials(db, symbols)

            await _log_job_execution(
                db=db,
                job_name=job_name,
                run_id=run_id,
                status=result.status,
                started_at=started_at,
                finished_at=result.finished_at,
                processed_count=result.total_statements,
                details=_financial_success_details(job_name, symbols, trigger, reporting_mode=False),
            )

            logger.info(
                f"{job_name}: Completed - status={result.status}, "
                f"statements={result.total_statements}"
            )

        except Exception as e:
            logger.exception(f"{job_name}: Failed with error")
            await _log_job_execution(
                db=db,
                job_name=job_name,
                run_id=run_id,
                status="failed",
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
                error_message=str(e),
                details={"trigger": trigger, "job_name": job_name, "reporting_mode": False},
            )


async def run_financials_reporting_job(
    *,
    symbols: list[str] | None = None,
    trigger: str = "scheduled",
    run_id: str | None = None,
) -> None:
    """Execute 4-hourly financial sync job (only if reporting mode is active)."""
    job_name = "financials_sync_reporting"
    run_id = run_id or str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as db:
        try:
            # Check reporting mode
            if trigger == "scheduled" and not await _check_reporting_mode(db):
                logger.info(f"{job_name}: Reporting mode off, skipping")
                await _log_skipped_job(db, job_name, "reporting_mode_off", trigger=trigger, run_id=run_id)
                return

            # Get universe (BIST100)
            symbols = symbols or await get_bist100_symbols_from_provider()
            logger.info(f"{job_name}: Syncing {len(symbols)} symbols (reporting mode)")

            # Execute sync
            result = await batch_sync_financials(db, symbols)

            await _log_job_execution(
                db=db,
                job_name=job_name,
                run_id=run_id,
                status=result.status,
                started_at=started_at,
                finished_at=result.finished_at,
                processed_count=result.total_statements,
                details=_financial_success_details(job_name, symbols, trigger, reporting_mode=True),
            )

            logger.info(
                f"{job_name}: Completed - status={result.status}, "
                f"statements={result.total_statements}"
            )

        except Exception as e:
            logger.exception(f"{job_name}: Failed with error")
            await _log_job_execution(
                db=db,
                job_name=job_name,
                run_id=run_id,
                status="failed",
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
                error_message=str(e),
                details={"trigger": trigger, "job_name": job_name, "reporting_mode": True},
            )


async def run_kap_sync_job(
    *,
    job_name: str,
    symbols: list[str],
    trigger: str = "scheduled",
    run_id: str | None = None,
    universe: str,
    filing_types: list[str] | None = None,
    days_back: int = 30,
) -> None:
    """Execute a KAP sync job for a provided symbol universe."""
    run_id = run_id or str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)
    filing_types = filing_types or ["FR"]

    async with AsyncSessionLocal() as db:
        try:
            if not symbols:
                logger.info(f"{job_name}: No symbols, skipping")
                await _log_skipped_job(
                    db,
                    job_name,
                    f"no_{universe}_symbols",
                    trigger=trigger,
                    run_id=run_id,
                    details={"universe": universe},
                )
                return

            logger.info(f"{job_name}: Syncing {len(symbols)} symbols")

            result = await batch_sync_kap_filings(
                db, symbols, filing_types=filing_types, days_back=days_back
            )

            await _log_job_execution(
                db=db,
                job_name=job_name,
                run_id=run_id,
                status=result.status,
                started_at=started_at,
                finished_at=result.finished_at,
                processed_count=result.total_processed,
                details=_kap_success_details(job_name, symbols, trigger, universe, filing_types, days_back),
            )

            logger.info(
                f"{job_name}: Completed - status={result.status}, "
                f"processed={result.total_processed}"
            )

        except Exception as e:
            logger.exception(f"{job_name}: Failed with error")
            await _log_job_execution(
                db=db,
                job_name=job_name,
                run_id=run_id,
                status="failed",
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
                error_message=str(e),
                details={
                    "trigger": trigger,
                    "job_name": job_name,
                    "universe": universe,
                    "filing_types": filing_types,
                    "days_back": days_back,
                },
            )


async def run_news_sync_hourly_job(
    *,
    symbols: list[str] | None = None,
    trigger: str = "scheduled",
    run_id: str | None = None,
) -> None:
    """Execute hourly news sync for BIST100."""
    if symbols is None:
        symbols = await get_bist100_symbols_from_provider()
    await run_kap_sync_job(
        job_name="news_sync_hourly",
        symbols=symbols,
        trigger=trigger,
        run_id=run_id,
        universe="bist100",
        filing_types=["ODA", "DG"],
        days_back=3,
    )


async def run_news_sync_watchlist_job(
    *,
    symbols: list[str] | None = None,
    trigger: str = "scheduled",
    run_id: str | None = None,
) -> None:
    """Execute daily news sync for watchlist stocks."""
    if symbols is None:
        async with AsyncSessionLocal() as db:
            symbols = await get_watchlist_symbols(db)
    await run_kap_sync_job(
        job_name="news_sync_watchlist",
        symbols=symbols,
        trigger=trigger,
        run_id=run_id,
        universe="watchlist",
        filing_types=["ODA", "DG"],
        days_back=3,
    )


async def run_news_sync_slow_job(
    *,
    symbols: list[str] | None = None,
    trigger: str = "scheduled",
    run_id: str | None = None,
) -> None:
    """Execute slow news sync for non-priority active stocks."""
    if symbols is None:
        async with AsyncSessionLocal() as db:
            symbols = await get_non_priority_active_symbols(db)
    await run_kap_sync_job(
        job_name="news_sync_slow",
        symbols=symbols,
        trigger=trigger,
        run_id=run_id,
        universe="slow",
        filing_types=["ODA", "DG"],
        days_back=7,
    )


async def run_report_sync_biweekly_job(
    *,
    symbols: list[str] | None = None,
    trigger: str = "scheduled",
    run_id: str | None = None,
) -> None:
    """Execute bi-weekly report sync for all active stocks."""
    settings = get_settings()
    if symbols is None:
        async with AsyncSessionLocal() as db:
            symbols = await get_all_active_symbols(db)
    await run_kap_sync_job(
        job_name="report_sync_biweekly",
        symbols=symbols,
        trigger=trigger,
        run_id=run_id,
        universe="all_active",
        filing_types=["FR", "FAR"],
        days_back=max(settings.report_sync_interval_days, 14),
    )


async def run_kap_hourly_job(*, symbols: list[str] | None = None, trigger: str = "scheduled", run_id: str | None = None) -> None:
    """Backward-compatible alias for hourly news sync."""
    await run_news_sync_hourly_job(symbols=symbols, trigger=trigger, run_id=run_id)


async def run_kap_watchlist_daily_job(*, symbols: list[str] | None = None, trigger: str = "scheduled", run_id: str | None = None) -> None:
    """Backward-compatible alias for watchlist news sync."""
    await run_news_sync_watchlist_job(symbols=symbols, trigger=trigger, run_id=run_id)


async def run_kap_slow_job(*, symbols: list[str] | None = None, trigger: str = "scheduled", run_id: str | None = None) -> None:
    """Backward-compatible alias for slow news sync."""
    await run_news_sync_slow_job(symbols=symbols, trigger=trigger, run_id=run_id)


async def run_pdf_download_job(
    *,
    limit: int | None = None,
    trigger: str = "scheduled",
    run_id: str | None = None,
) -> None:
    """Execute PDF download job for pending and failed downloads.

    This scheduler wrapper is THE ONLY place that creates PipelineLog.
    Service functions return results, NOT logs.
    """
    scheduler_job_id = "pdf_download_hourly"  # APScheduler job ID
    pipeline_name = "pdf_download_sync"       # PipelineLog.pipeline_name
    run_id = run_id or str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)

    # Default limit from config
    from app.config import get_settings
    settings = get_settings()
    limit = limit or settings.pdf_max_downloads_per_run

    async with AsyncSessionLocal() as db:
        try:
            logger.info(f"{scheduler_job_id}: Starting PDF downloads (limit={limit})")

            # Phase 1: Download pending PDFs (service returns result, no log)
            pending_result = await batch_download_pending_pdfs(
                db, limit=limit, filing_types=["FR", "FAR", "ODA"]
            )

            # Phase 2: Retry failed downloads (remaining slots)
            if pending_result.total_processed < limit:
                remaining = limit - pending_result.total_processed
                retry_result = await batch_retry_failed_downloads(
                    db, limit=remaining, filing_types=["FR", "FAR", "ODA"]
                )
                # Combine results for final log
                total_processed = pending_result.total_processed + retry_result.total_processed
                successful = pending_result.successful + retry_result.successful
                failed = pending_result.failed + retry_result.failed
                not_available = pending_result.not_available + retry_result.not_available
                status = "success" if failed == 0 else "partial"
            else:
                total_processed = pending_result.total_processed
                successful = pending_result.successful
                failed = pending_result.failed
                not_available = pending_result.not_available
                status = pending_result.status

            # THE ONLY PipelineLog creation for this run
            await _log_job_execution(
                db=db,
                job_name=pipeline_name,  # PipelineLog.pipeline_name = "pdf_download_sync"
                run_id=run_id,
                status=status,
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
                processed_count=total_processed,
                details={
                    "pipeline_name": pipeline_name,
                    "trigger": trigger,
                    "scheduler_job_id": scheduler_job_id,
                    "successful": successful,
                    "failed": failed,
                    "not_available": not_available,
                    "limit": limit,
                },
            )

            logger.info(
                f"{scheduler_job_id}: Completed - status={status}, "
                f"downloaded={successful}, failed={failed}, not_available={not_available}"
            )

        except Exception as e:
            logger.exception(f"{scheduler_job_id}: Failed with error")
            await _log_job_execution(
                db=db,
                job_name=pipeline_name,
                run_id=run_id,
                status="failed",
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
                error_message=str(e),
                details={
                    "trigger": trigger,
                    "pipeline_name": pipeline_name,
                    "scheduler_job_id": scheduler_job_id,
                },
            )


async def run_chunking_job(
    *,
    limit: int | None = None,
    trigger: str = "scheduled",
    run_id: str | None = None,
) -> None:
    """Execute chunking job for completed PDFs.

    This scheduler wrapper is THE ONLY place that creates PipelineLog.
    Service functions return results, NOT logs.
    """
    scheduler_job_id = "chunking_hourly"
    pipeline_name = "chunking_sync"
    run_id = run_id or str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)

    # Default limit from config
    from app.config import get_settings
    settings = get_settings()
    limit = limit or settings.chunk_max_per_run

    async with AsyncSessionLocal() as db:
        try:
            logger.info(f"{scheduler_job_id}: Starting chunking (limit={limit})")

            # Execute chunking (service returns result, no log)
            result = await batch_chunk_completed_pdfs(db, limit=limit)

            # THE ONLY PipelineLog creation for this run
            await _log_job_execution(
                db=db,
                job_name=pipeline_name,
                run_id=run_id,
                status=result.status,
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
                processed_count=result.total_processed,
                details={
                    "pipeline_name": pipeline_name,
                    "trigger": trigger,
                    "scheduler_job_id": scheduler_job_id,
                    "successful": result.successful,
                    "failed": result.failed,
                    "limit": limit,
                },
            )

            logger.info(
                f"{scheduler_job_id}: Completed - status={result.status}, "
                f"processed={result.total_processed}, successful={result.successful}, failed={result.failed}"
            )

        except Exception as e:
            logger.exception(f"{scheduler_job_id}: Failed with error")
            await _log_job_execution(
                db=db,
                job_name=pipeline_name,
                run_id=run_id,
                status="failed",
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
                error_message=str(e),
                details={
                    "trigger": trigger,
                    "pipeline_name": pipeline_name,
                    "scheduler_job_id": scheduler_job_id,
                },
            )


async def run_embedding_job(
    *,
    limit: int | None = None,
    trigger: str = "scheduled",
    run_id: str | None = None,
) -> None:
    """Execute embedding job for pending chunks.

    This scheduler wrapper is THE ONLY place that creates PipelineLog.
    Service functions return results, NOT logs.
    """
    scheduler_job_id = "embedding_10min"
    pipeline_name = "embedding_sync"
    run_id = run_id or str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)

    # Default limit from config
    from app.config import get_settings
    settings = get_settings()
    limit = limit or settings.embedding_max_per_run

    async with AsyncSessionLocal() as db:
        try:
            logger.info(f"{scheduler_job_id}: Starting embedding (limit={limit})")

            # Execute embedding (service returns result, no log)
            result = await batch_embed_pending_chunks(db, limit=limit)

            # THE ONLY PipelineLog creation for this run
            await _log_job_execution(
                db=db,
                job_name=pipeline_name,
                run_id=run_id,
                status=result.status,
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
                processed_count=result.total_processed,
                details={
                    "pipeline_name": pipeline_name,
                    "trigger": trigger,
                    "scheduler_job_id": scheduler_job_id,
                    "successful": result.successful,
                    "failed": result.failed,
                    "limit": limit,
                    "api_batch_size": settings.embedding_batch_size,
                },
            )

            logger.info(
                f"{scheduler_job_id}: Completed - status={result.status}, "
                f"processed={result.total_processed}, successful={result.successful}, failed={result.failed}"
            )

        except Exception as e:
            logger.exception(f"{scheduler_job_id}: Failed with error")
            await _log_job_execution(
                db=db,
                job_name=pipeline_name,
                run_id=run_id,
                status="failed",
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
                error_message=str(e),
                details={
                    "trigger": trigger,
                    "pipeline_name": pipeline_name,
                    "scheduler_job_id": scheduler_job_id,
                },
            )


# ============================================================================
# Scheduler Lifecycle
# ============================================================================


async def start_scheduler() -> None:
    """Start the scheduler and register all jobs."""
    logger.info("Starting scheduler...")
    settings = get_settings()

    # Job 1: Price sync - every 15 minutes
    scheduler.add_job(
        run_price_sync_job,
        trigger=IntervalTrigger(minutes=15),
        id="price_sync",
        name="Price Sync (15min)",
        replace_existing=True,
    )

    # Job 2a: Financials weekly - every Monday at 06:00
    scheduler.add_job(
        run_financials_weekly_job,
        trigger=CronTrigger(day_of_week="mon", hour=6, minute=0, timezone="Europe/Istanbul"),
        id="financials_sync_weekly",
        name="Financials Sync Weekly",
        replace_existing=True,
    )

    scheduler.add_job(
        run_snapshot_sync_daily_job,
        trigger=CronTrigger(hour=23, minute=0, timezone="Europe/Istanbul"),
        id="snapshot_sync_daily",
        name="Snapshot Sync Daily",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
    )

    # Job 2b: Financials reporting - every 4 hours
    scheduler.add_job(
        run_financials_reporting_job,
        trigger=IntervalTrigger(hours=4),
        id="financials_sync_reporting",
        name="Financials Sync Reporting (4h)",
        replace_existing=True,
    )

    if settings.news_sync_hourly_enabled:
        scheduler.add_job(
            run_news_sync_hourly_job,
            trigger=IntervalTrigger(hours=1),
            id="news_sync_hourly",
            name="News Sync Hourly",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=1800,
        )

    scheduler.add_job(
        run_news_sync_watchlist_job,
        trigger=CronTrigger(
            hour=settings.news_sync_watchlist_hour,
            minute=0,
            timezone="Europe/Istanbul",
        ),
        id="news_sync_watchlist",
        name="News Sync Watchlist Daily",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
    )

    scheduler.add_job(
        run_news_sync_slow_job,
        trigger=CronTrigger(
            day=f"*/{settings.news_sync_slow_interval_days}",
            hour=settings.news_sync_slow_hour,
            minute=0,
            timezone="Europe/Istanbul",
        ),
        id="news_sync_slow",
        name="News Sync Slow",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=7200,
    )

    scheduler.add_job(
        run_report_sync_biweekly_job,
        trigger=_build_report_sync_trigger(),
        id="report_sync_biweekly",
        name="Report Sync Biweekly",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=7200,
    )

    if settings.pdf_download_hourly_enabled:
        scheduler.add_job(
            run_pdf_download_job,
            trigger=IntervalTrigger(hours=1),
            id="pdf_download_hourly",
            name="PDF Download Hourly",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=1800,
        )

    # Job 7: Chunking - hourly (process PDFs that completed download)
    scheduler.add_job(
        run_chunking_job,
        trigger=IntervalTrigger(hours=1),
        id="chunking_hourly",
        name="Chunking Hourly",
        replace_existing=True,
    )

    # Job 8: Embedding - every 10 minutes (embed pending chunks)
    scheduler.add_job(
        run_embedding_job,
        trigger=IntervalTrigger(minutes=10),
        id="embedding_10min",
        name="Embedding (10min)",
        replace_existing=True,
    )

    scheduler.start()
    logger.info(
        f"Scheduler started with {len(scheduler.get_jobs())} jobs: "
        f"{[j.id for j in scheduler.get_jobs()]}"
    )


async def stop_scheduler() -> None:
    """Stop the scheduler gracefully."""
    logger.info("Stopping scheduler...")
    scheduler.shutdown(wait=True)
    logger.info("Scheduler stopped")


def get_scheduler_status() -> dict:
    """Get current scheduler status."""
    jobs = scheduler.get_jobs()
    return {
        "is_running": scheduler.running,
        "jobs": [
            {
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            }
            for job in jobs
        ],
    }
