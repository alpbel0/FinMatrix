"""Mapper helpers for stock snapshot persistence."""

from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pipeline_log import PipelineLog
from app.models.stock import Stock
from app.models.stock_snapshot import StockSnapshotRecord
from app.services.data.mappers.snapshot_normalizer import SNAPSHOT_FIELDS


async def get_stock_snapshot_latest(db: AsyncSession, symbol: str) -> StockSnapshotRecord | None:
    stock_id = await _get_stock_id_by_symbol(db, symbol)
    if stock_id is None:
        return None

    result = await db.execute(
        select(StockSnapshotRecord)
        .where(StockSnapshotRecord.stock_id == stock_id)
        .order_by(StockSnapshotRecord.snapshot_date.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_stock_snapshot_history(
    db: AsyncSession,
    symbol: str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[StockSnapshotRecord]:
    stock_id = await _get_stock_id_by_symbol(db, symbol)
    if stock_id is None:
        return []

    query = select(StockSnapshotRecord).where(StockSnapshotRecord.stock_id == stock_id)
    if start_date is not None:
        query = query.where(StockSnapshotRecord.snapshot_date >= start_date)
    if end_date is not None:
        query = query.where(StockSnapshotRecord.snapshot_date <= end_date)

    result = await db.execute(query.order_by(StockSnapshotRecord.snapshot_date.asc()))
    return list(result.scalars().all())


async def get_latest_snapshot_before_date(
    db: AsyncSession,
    stock_id: int,
    snapshot_date: date,
) -> StockSnapshotRecord | None:
    result = await db.execute(
        select(StockSnapshotRecord)
        .where(StockSnapshotRecord.stock_id == stock_id)
        .where(StockSnapshotRecord.snapshot_date < snapshot_date)
        .order_by(StockSnapshotRecord.snapshot_date.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_last_successful_snapshot_sync_at(db: AsyncSession) -> datetime | None:
    result = await db.execute(
        select(PipelineLog)
        .where(PipelineLog.pipeline_name == "snapshot_sync_daily")
        .where(PipelineLog.status.in_(["success", "partial"]))
        .order_by(PipelineLog.finished_at.desc())
        .limit(1)
    )
    log = result.scalar_one_or_none()
    return log.finished_at if log else None


async def upsert_stock_snapshot(
    db: AsyncSession,
    stock_id: int,
    snapshot_date: date,
    payload: dict,
    commit: bool = True,
) -> StockSnapshotRecord:
    values = {
        "stock_id": stock_id,
        "snapshot_date": snapshot_date,
        **{field: payload.get(field) for field in SNAPSHOT_FIELDS},
        "source": payload.get("source", "borsapy"),
        "field_sources": payload.get("field_sources"),
        "missing_fields_count": payload.get("missing_fields_count", 0),
        "completeness_score": payload.get("completeness_score", 0.0),
        "is_partial": payload.get("is_partial", False),
        "fetched_at": payload.get("fetched_at") or datetime.now(timezone.utc),
    }

    stmt = insert(StockSnapshotRecord).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["stock_id", "snapshot_date"],
        set_={
            **{field: getattr(stmt.excluded, field) for field in SNAPSHOT_FIELDS},
            "source": stmt.excluded.source,
            "field_sources": stmt.excluded.field_sources,
            "missing_fields_count": stmt.excluded.missing_fields_count,
            "completeness_score": stmt.excluded.completeness_score,
            "is_partial": stmt.excluded.is_partial,
            "fetched_at": stmt.excluded.fetched_at,
            "updated_at": func.now(),
        },
    ).returning(StockSnapshotRecord)

    result = await db.execute(stmt)
    if commit:
        await db.commit()
    return result.scalar_one()


async def _get_stock_id_by_symbol(db: AsyncSession, symbol: str) -> int | None:
    result = await db.execute(select(Stock.id).where(Stock.symbol == symbol.upper()))
    return result.scalar_one_or_none()
