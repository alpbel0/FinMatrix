"""Stock snapshot ingestion and query service."""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pipeline_log import PipelineLog
from app.models.stock import Stock
from app.models.sync_job_run import SyncJobRun
from app.services.analytics.metric_engine import MetricEngine
from app.services.data.mappers.snapshot_normalizer import normalize_snapshot_payload
from app.services.data.mappers.stock_snapshot_mapper import (
    SNAPSHOT_FIELDS,
    get_last_successful_snapshot_sync_at,
    get_stock_snapshot_history,
    get_stock_snapshot_latest,
    upsert_stock_snapshot,
)
from app.services.data.provider_exceptions import ProviderError
from app.services.data.providers.snapshot_provider import RawSnapshotPayload, get_snapshot_provider
from app.services.utils.logging import logger


ISTANBUL_TZ = ZoneInfo("Europe/Istanbul")
DEFAULT_CONCURRENCY = 5
DEFAULT_CHUNK_SIZE = 50


class SnapshotSyncResult(BaseModel):
    symbol: str
    success: bool
    is_partial: bool = False
    snapshot_date: date | None = None
    missing_fields_count: int = 0
    completeness_score: float = 0.0
    error_message: str | None = None


class SnapshotBatchSyncResult(BaseModel):
    pipeline_name: str
    run_id: str
    status: str
    started_at: datetime
    finished_at: datetime
    total_processed: int
    successful: list[str]
    partial: list[str]
    failed: list[SnapshotSyncResult]
    details: dict | None = None


@dataclass
class _FetchedSnapshot:
    symbol: str
    stock_id: int
    primary_snapshot: RawSnapshotPayload | None = None
    supplement_snapshots: list[RawSnapshotPayload] = field(default_factory=list)
    error_message: str | None = None


async def sync_stock_snapshot(
    db: AsyncSession,
    symbol: str,
    snapshot_date: date | None = None,
) -> SnapshotSyncResult:
    """Backward-compatible wrapper for syncing one stock by symbol."""
    symbol = symbol.upper()
    snapshot_date = snapshot_date or _today_istanbul()

    stock = await _get_stock(db, symbol)
    if stock is None:
        return SnapshotSyncResult(
            symbol=symbol,
            success=False,
            error_message=f"Stock {symbol} not found in database",
        )

    return await sync_one_stock_snapshot(db, stock.id, snapshot_date=snapshot_date)


async def sync_one_stock_snapshot(
    db: AsyncSession,
    stock_id: int,
    snapshot_date: date | None = None,
) -> SnapshotSyncResult:
    """Fetch, normalize, score, and upsert one stock snapshot by stock id."""
    snapshot_date = snapshot_date or _today_istanbul()

    stock = await _get_stock_by_id(db, stock_id)
    if stock is None:
        return SnapshotSyncResult(
            symbol=f"stock_id:{stock_id}",
            success=False,
            error_message=f"Stock id {stock_id} not found in database",
        )

    fetched = await _fetch_provider_snapshot(stock.id, stock.symbol)
    if fetched.error_message:
        return SnapshotSyncResult(symbol=stock.symbol, success=False, error_message=fetched.error_message)

    payload = await _build_snapshot_payload(
        db,
        stock.id,
        snapshot_date,
        fetched.primary_snapshot,
        fetched.supplement_snapshots,
    )
    persisted = await upsert_stock_snapshot(db, stock.id, snapshot_date, payload)
    return SnapshotSyncResult(
        symbol=stock.symbol,
        success=True,
        is_partial=persisted.is_partial,
        snapshot_date=persisted.snapshot_date,
        missing_fields_count=persisted.missing_fields_count,
        completeness_score=persisted.completeness_score,
    )


async def batch_sync_stock_snapshots(
    db: AsyncSession,
    symbols: list[str],
    snapshot_date: date | None = None,
    concurrency: int = DEFAULT_CONCURRENCY,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    run_id: str | None = None,
    trigger: str = "scheduled",
) -> SnapshotBatchSyncResult:
    """Backward-compatible wrapper for syncing an explicit stock symbol list."""
    run_id = run_id or str(uuid.uuid4())
    pipeline_name = "snapshot_sync_daily"
    started_at = datetime.now(timezone.utc)
    snapshot_date = snapshot_date or _today_istanbul()

    valid_stocks = await _get_stocks_by_symbols(db, symbols)
    sync_job_run = await _create_snapshot_job_run(
        db,
        job_name=pipeline_name,
        run_date=snapshot_date,
        total_stocks=len(valid_stocks),
        details={
            "run_id": run_id,
            "trigger": trigger,
            "mode": "explicit_symbols",
            "requested_symbols": [symbol.upper() for symbol in symbols],
        },
    )

    if not valid_stocks:
        finished_at = datetime.now(timezone.utc)
        result = SnapshotBatchSyncResult(
            pipeline_name=pipeline_name,
            run_id=run_id,
            status="success",
            started_at=started_at,
            finished_at=finished_at,
            total_processed=0,
            successful=[],
            partial=[],
            failed=[],
            details={
                "job_name": pipeline_name,
                "trigger": trigger,
                "symbol_count": 0,
                "snapshot_date": snapshot_date.isoformat(),
                "mode": "explicit_symbols",
            },
        )
        await _finalize_snapshot_job_run(db, sync_job_run, result)
        await _create_snapshot_pipeline_log(db, run_id, started_at, result)
        return result

    chunks = [valid_stocks[index:index + chunk_size] for index in range(0, len(valid_stocks), chunk_size)]

    fetched_items: list[_FetchedSnapshot] = []
    for chunk in chunks:
        fetched_items.extend(
            await _fetch_snapshot_chunk(
                chunk,
                concurrency=concurrency,
            )
        )

    successful: list[str] = []
    partial: list[str] = []
    failed: list[SnapshotSyncResult] = []

    for fetched in fetched_items:
        if fetched.error_message:
            failed.append(
                SnapshotSyncResult(symbol=fetched.symbol, success=False, error_message=fetched.error_message)
            )
            continue

        payload = await _build_snapshot_payload(
            db,
            fetched.stock_id,
            snapshot_date,
            fetched.primary_snapshot,
            fetched.supplement_snapshots,
        )
        persisted = await upsert_stock_snapshot(
            db,
            fetched.stock_id,
            snapshot_date,
            payload,
            commit=False,
        )
        if persisted.is_partial:
            partial.append(fetched.symbol)
        else:
            successful.append(fetched.symbol)

    finished_at = datetime.now(timezone.utc)
    status = _derive_batch_status(successful, partial, failed)
    details = {
        "job_name": pipeline_name,
        "trigger": trigger,
        "symbol_count": len(valid_stocks),
        "successful_symbols": successful,
        "partial_symbols": partial,
        "failed_symbols": [item.symbol for item in failed],
        "chunk_size": chunk_size,
        "concurrency": concurrency,
        "snapshot_date": snapshot_date.isoformat(),
    }

    result = SnapshotBatchSyncResult(
        pipeline_name=pipeline_name,
        run_id=run_id,
        status=status,
        started_at=started_at,
        finished_at=finished_at,
        total_processed=len(successful) + len(partial),
        successful=successful,
        partial=partial,
        failed=failed,
        details=details,
    )
    await _finalize_snapshot_job_run(db, sync_job_run, result)
    await _create_snapshot_pipeline_log(db, run_id, started_at, result)
    return result


async def sync_all_active_stock_snapshots(
    db: AsyncSession,
    snapshot_date: date | None = None,
    concurrency: int = DEFAULT_CONCURRENCY,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    run_id: str | None = None,
    trigger: str = "scheduled",
) -> SnapshotBatchSyncResult:
    """Sync snapshots for every active stock in the stocks table."""
    active_stocks = await _get_all_active_stocks(db)
    symbols = [stock.symbol for stock in active_stocks]
    return await batch_sync_stock_snapshots(
        db,
        symbols,
        snapshot_date=snapshot_date,
        concurrency=concurrency,
        chunk_size=chunk_size,
        run_id=run_id,
        trigger=trigger,
    )


async def get_latest_stock_snapshot_payload(db: AsyncSession, symbol: str) -> dict:
    symbol = symbol.upper()
    stock = await _get_stock(db, symbol)
    if stock is None:
        raise ValueError(f"Stock '{symbol}' not found")

    snapshot = await get_stock_snapshot_latest(db, symbol)
    last_successful_sync_at = await get_last_successful_snapshot_sync_at(db)
    freshness = _build_freshness(snapshot.snapshot_date if snapshot else None)

    response = {
        "symbol": symbol,
        "snapshot_date": snapshot.snapshot_date if snapshot else None,
        "fetched_at": snapshot.fetched_at if snapshot else None,
        "source": snapshot.source if snapshot else None,
        "field_sources": snapshot.field_sources if snapshot else None,
        "is_partial": snapshot.is_partial if snapshot else True,
        "completeness_score": snapshot.completeness_score if snapshot else 0.0,
        "missing_fields_count": snapshot.missing_fields_count if snapshot else len(SNAPSHOT_FIELDS),
        "is_stale": freshness["is_stale"],
        "stale_reason": freshness["stale_reason"],
        "last_successful_sync_at": last_successful_sync_at,
    }
    for field in SNAPSHOT_FIELDS:
        response[field] = getattr(snapshot, field) if snapshot else None
    return response


async def get_historical_stock_snapshots_payload(
    db: AsyncSession,
    symbol: str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    stock = await _get_stock(db, symbol)
    if stock is None:
        raise ValueError(f"Stock '{symbol}' not found")

    snapshots = await get_stock_snapshot_history(db, symbol, start_date, end_date)
    return {
        "symbol": symbol.upper(),
        "snapshots": [
            {
                "snapshot_date": snapshot.snapshot_date,
                **{field: getattr(snapshot, field) for field in SNAPSHOT_FIELDS},
                "source": snapshot.source,
                "field_sources": snapshot.field_sources,
                "is_partial": snapshot.is_partial,
                "completeness_score": snapshot.completeness_score,
            }
            for snapshot in snapshots
        ],
        "count": len(snapshots),
    }


async def _fetch_snapshot_chunk(
    stocks: list[Stock],
    concurrency: int,
) -> list[_FetchedSnapshot]:
    semaphore = asyncio.Semaphore(concurrency)
    tasks = [
        asyncio.create_task(
            _fetch_snapshot_for_stock(
                stock.id,
                stock.symbol,
                semaphore,
            )
        )
        for stock in stocks
    ]
    return await asyncio.gather(*tasks)


async def _fetch_snapshot_for_stock(
    stock_id: int,
    symbol: str,
    semaphore: asyncio.Semaphore,
) -> _FetchedSnapshot:
    async with semaphore:
        return await _fetch_provider_snapshot(stock_id, symbol)


async def _fetch_provider_snapshot(stock_id: int, symbol: str) -> _FetchedSnapshot:
    provider = get_snapshot_provider()
    try:
        fetched = await asyncio.to_thread(provider.fetch_snapshot, symbol)
        return _FetchedSnapshot(
            symbol=symbol,
            stock_id=stock_id,
            primary_snapshot=fetched.primary,
            supplement_snapshots=fetched.supplements,
        )
    except ProviderError as exc:
        logger.warning("Snapshot sync failed for %s: %s", symbol, exc)
        return _FetchedSnapshot(symbol=symbol, stock_id=stock_id, error_message=str(exc))
    except Exception as exc:
        logger.exception("Unexpected snapshot sync failure for %s", symbol)
        return _FetchedSnapshot(symbol=symbol, stock_id=stock_id, error_message=str(exc))


async def _get_stock(db: AsyncSession, symbol: str) -> Stock | None:
    result = await db.execute(select(Stock).where(Stock.symbol == symbol.upper()))
    return result.scalar_one_or_none()


async def _get_stock_by_id(db: AsyncSession, stock_id: int) -> Stock | None:
    result = await db.execute(select(Stock).where(Stock.id == stock_id))
    return result.scalar_one_or_none()


async def _get_stocks_by_symbols(db: AsyncSession, symbols: list[str]) -> list[Stock]:
    normalized = [symbol.upper() for symbol in symbols]
    result = await db.execute(
        select(Stock)
        .where(Stock.symbol.in_(normalized))
        .where(Stock.is_active == True)
        .order_by(Stock.symbol.asc())
    )
    return list(result.scalars().all())


async def _get_all_active_stocks(db: AsyncSession) -> list[Stock]:
    result = await db.execute(
        select(Stock)
        .where(Stock.is_active == True)
        .order_by(Stock.symbol.asc())
    )
    return list(result.scalars().all())


async def _build_snapshot_payload(
    db: AsyncSession,
    stock_id: int,
    snapshot_date: date,
    provider_snapshot,
    supplement_snapshots: list[RawSnapshotPayload] | None = None,
) -> dict:
    provider_payload = normalize_snapshot_payload(
        provider_snapshot,
        supplements=supplement_snapshots,
    )
    engine = MetricEngine(db)
    return await engine.build_snapshot_payload(stock_id, snapshot_date, provider_payload)


async def _create_snapshot_job_run(
    db: AsyncSession,
    *,
    job_name: str,
    run_date: date,
    total_stocks: int,
    details: dict | None = None,
) -> SyncJobRun:
    job_run = SyncJobRun(
        job_name=job_name,
        run_date=run_date,
        status="running",
        total_stocks=total_stocks,
        success_count=0,
        partial_count=0,
        failed_count=0,
        details=details,
    )
    db.add(job_run)
    await db.flush()
    return job_run


async def _finalize_snapshot_job_run(
    db: AsyncSession,
    job_run: SyncJobRun,
    result: SnapshotBatchSyncResult,
) -> None:
    existing_details = dict(job_run.details or {})
    existing_details.update(result.details or {})
    existing_details["successful_symbols"] = result.successful
    existing_details["partial_symbols"] = result.partial
    existing_details["failed_symbols"] = [item.symbol for item in result.failed]

    job_run.status = result.status
    job_run.finished_at = result.finished_at
    job_run.success_count = len(result.successful)
    job_run.partial_count = len(result.partial)
    job_run.failed_count = len(result.failed)
    job_run.error_message = (
        "; ".join(filter(None, [item.error_message for item in result.failed]))[:500]
        if result.failed
        else None
    )
    job_run.details = existing_details
    await db.flush()


async def _create_snapshot_pipeline_log(
    db: AsyncSession,
    run_id: str,
    started_at: datetime,
    result: SnapshotBatchSyncResult,
) -> None:
    log = PipelineLog(
        run_id=run_id,
        pipeline_name=result.pipeline_name,
        status=result.status,
        started_at=started_at,
        finished_at=result.finished_at,
        processed_count=result.total_processed,
        error_message=(
            "; ".join(filter(None, [item.error_message for item in result.failed]))[:500]
            if result.failed
            else None
        ),
        details=result.details,
    )
    db.add(log)
    await db.commit()


def _derive_batch_status(successful: list[str], partial: list[str], failed: list[SnapshotSyncResult]) -> str:
    if failed and not successful and not partial:
        return "failed"
    if failed:
        return "partial"
    if partial:
        return "partial"
    return "success"


def _build_freshness(snapshot_date: date | None) -> dict[str, str | bool | None]:
    today = _today_istanbul()
    now = datetime.now(ISTANBUL_TZ)

    if snapshot_date is None:
        return {"is_stale": True, "stale_reason": "no_snapshot"}
    if snapshot_date == today:
        return {"is_stale": False, "stale_reason": None}
    if today.weekday() >= 5:
        return {"is_stale": True, "stale_reason": "market_closed"}

    previous_business_day = _previous_business_day(today)
    if now.hour < 23 and snapshot_date == previous_business_day:
        return {"is_stale": True, "stale_reason": "awaiting_daily_sync"}
    return {"is_stale": True, "stale_reason": "sync_delayed"}


def _today_istanbul() -> date:
    return datetime.now(ISTANBUL_TZ).date()


def _previous_business_day(current_day: date) -> date:
    previous_day = current_day - timedelta(days=1)
    while previous_day.weekday() >= 5:
        previous_day -= timedelta(days=1)
    return previous_day
