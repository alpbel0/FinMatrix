"""Market data ingestion service.

Orchestrates provider fetch + mapper upsert + PipelineLog tracking
for price history data.
"""

import asyncio
import uuid
from datetime import datetime, date, timezone
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pipeline_log import PipelineLog
from app.models.stock import Stock
from app.services.data.mappers.stock_price_mapper import upsert_price_bars
from app.services.data.provider_exceptions import (
    ProviderConnectionError,
    ProviderTimeoutError,
    ProviderRateLimitError,
    ProviderSymbolNotFoundError,
    ProviderDataNotFoundError,
    ProviderAPIError,
)
from app.services.data.provider_registry import get_provider_for_prices
from app.services.data.provider_models import PriceBar
from app.services.utils.logging import logger


# ============================================================================
# Result Models
# ============================================================================


class SyncResult(BaseModel):
    """Result of a sync operation for a single symbol."""

    symbol: str
    success: bool
    records_processed: int = 0
    error_message: str | None = None
    duration_seconds: float | None = None


class BatchSyncResult(BaseModel):
    """Result of a batch sync operation."""

    pipeline_name: str
    run_id: str
    status: str  # "success", "partial", "failed"
    started_at: datetime
    finished_at: datetime
    total_processed: int
    successful: list[str]
    failed: list[SyncResult]
    details: dict[str, Any] | None = None


# ============================================================================
# Retry Configuration
# ============================================================================

DEFAULT_RETRY_COUNT = 3
DEFAULT_RETRY_DELAY_BASE = 2  # Exponential backoff: 2^attempt seconds


# ============================================================================
# Service Functions
# ============================================================================


async def sync_price_history(
    db: AsyncSession,
    symbol: str,
    period: str = "1y",
    start_date: date | None = None,
    end_date: date | None = None,
    max_retries: int = DEFAULT_RETRY_COUNT,
) -> SyncResult:
    """
    Sync price history for a single symbol.

    Flow:
    1. Check stock exists in database
    2. Get provider (default: borsapy via registry)
    3. Fetch price bars from provider (sync -> async wrapper)
    4. Upsert to database via mapper
    5. Return result with success/failure details

    Args:
        db: AsyncSession
        symbol: Stock symbol (e.g., "THYAO")
        period: Predefined period ("1mo", "1y", "max")
        start_date: Optional start date for date range
        end_date: Optional end date for date range
        max_retries: Maximum retry attempts for transient errors

    Returns:
        SyncResult with success status and record count
    """
    symbol = symbol.upper()
    start_time = datetime.now(timezone.utc)

    # Check stock exists
    result = await db.execute(
        select(Stock.id).where(Stock.symbol == symbol)
    )
    stock_id = result.scalar_one_or_none()
    if stock_id is None:
        logger.warning(f"Stock {symbol} not found in database")
        return SyncResult(
            symbol=symbol,
            success=False,
            error_message=f"Stock {symbol} not found in database",
        )

    # Get provider
    provider = get_provider_for_prices()

    # Retry loop for transient errors. `attempt` counts only real retry-consuming failures.
    attempt = 0
    while attempt < max_retries:
        try:
            logger.info(f"Fetching price history for {symbol} (attempt {attempt + 1})...")

            # Provider is synchronous, wrap with asyncio.to_thread
            price_bars = await asyncio.to_thread(
                provider.get_price_history,
                symbol,
                start_date=start_date,
                end_date=end_date,
                period=period,
            )

            # Empty data is OK
            if not price_bars:
                logger.info(f"No price data returned for {symbol}")
                duration = (datetime.now(timezone.utc) - start_time).total_seconds()
                return SyncResult(
                    symbol=symbol,
                    success=True,
                    records_processed=0,
                    duration_seconds=duration,
                )

            # Upsert to database
            count = await upsert_price_bars(db, symbol, list(price_bars))

            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            logger.info(f"Synced {count} price bars for {symbol} in {duration:.2f}s")

            return SyncResult(
                symbol=symbol,
                success=True,
                records_processed=count,
                duration_seconds=duration,
            )

        except ProviderConnectionError as e:
            attempt += 1
            if attempt < max_retries:
                delay = DEFAULT_RETRY_DELAY_BASE ** (attempt - 1)
                logger.warning(
                    f"Connection error for {symbol}, retrying in {delay}s (attempt {attempt + 1}/{max_retries})"
                )
                await asyncio.sleep(delay)
            else:
                duration = (datetime.now(timezone.utc) - start_time).total_seconds()
                logger.error(f"Failed to sync {symbol} after {max_retries} attempts: {e}")
                return SyncResult(
                    symbol=symbol,
                    success=False,
                    error_message=f"Connection error after {max_retries} retries: {e}",
                    duration_seconds=duration,
                )

        except ProviderTimeoutError as e:
            attempt += 1
            if attempt < max_retries:
                delay = DEFAULT_RETRY_DELAY_BASE ** (attempt - 1)
                logger.warning(
                    f"Timeout for {symbol}, retrying in {delay}s (attempt {attempt + 1}/{max_retries})"
                )
                await asyncio.sleep(delay)
            else:
                duration = (datetime.now(timezone.utc) - start_time).total_seconds()
                logger.error(f"Failed to sync {symbol} after {max_retries} attempts: {e}")
                return SyncResult(
                    symbol=symbol,
                    success=False,
                    error_message=f"Timeout after {max_retries} retries: {e}",
                    duration_seconds=duration,
                )

        except ProviderRateLimitError as e:
            # Wait for retry_after if provided
            retry_after = getattr(e, 'retry_after', 60)
            logger.warning(f"Rate limited for {symbol}, waiting {retry_after}s")
            await asyncio.sleep(retry_after)
            # Don't count rate limit as a retry attempt
            continue

        except ProviderSymbolNotFoundError as e:
            # Non-retriable
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            logger.warning(f"Symbol {symbol} not found by provider: {e}")
            return SyncResult(
                symbol=symbol,
                success=False,
                error_message=f"Symbol not found: {e}",
                duration_seconds=duration,
            )

        except ProviderDataNotFoundError as e:
            # Empty data is OK, return success with 0 records
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            logger.info(f"No data found for {symbol}: {e}")
            return SyncResult(
                symbol=symbol,
                success=True,
                records_processed=0,
                duration_seconds=duration,
            )

        except ProviderAPIError as e:
            # Check if retriable (5xx) or non-retriable (4xx)
            status_code = getattr(e, 'status_code', None)
            if status_code and status_code >= 500:
                attempt += 1
            if status_code and status_code >= 500 and attempt < max_retries:
                delay = DEFAULT_RETRY_DELAY_BASE ** (attempt - 1)
                logger.warning(
                    f"API error {status_code} for {symbol}, retrying in {delay}s"
                )
                await asyncio.sleep(delay)
            else:
                duration = (datetime.now(timezone.utc) - start_time).total_seconds()
                logger.error(f"API error for {symbol}: {e}")
                return SyncResult(
                    symbol=symbol,
                    success=False,
                    error_message=f"API error: {e}",
                    duration_seconds=duration,
                )

        except Exception as e:
            # Unexpected error - log and fail
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            logger.error(f"Unexpected error syncing {symbol}: {e}")
            return SyncResult(
                symbol=symbol,
                success=False,
                error_message=f"Unexpected error: {e}",
                duration_seconds=duration,
            )

    # Should not reach here
    return SyncResult(
        symbol=symbol,
        success=False,
        error_message="Max retries exceeded",
    )


async def batch_sync_prices(
    db: AsyncSession,
    symbols: list[str],
    period: str = "1y",
) -> BatchSyncResult:
    """
    Batch sync price history for multiple symbols.

    Flow:
    1. Create PipelineLog entry (run_id = uuid4, status = "running")
    2. Iterate symbols with error handling
    3. Update PipelineLog with results
    4. Return BatchSyncResult

    Args:
        db: AsyncSession
        symbols: List of stock symbols
        period: Predefined period for all symbols

    Returns:
        BatchSyncResult with overall status and per-symbol results
    """
    run_id = str(uuid.uuid4())
    pipeline_name = "price_sync"
    started_at = datetime.now(timezone.utc)

    logger.info(f"Starting batch price sync (run_id={run_id}) for {len(symbols)} symbols")

    # Create initial PipelineLog entry
    log = PipelineLog(
        run_id=run_id,
        pipeline_name=pipeline_name,
        status="running",
        started_at=started_at,
        processed_count=0,
    )
    db.add(log)
    await db.commit()

    successful: list[str] = []
    failed: list[SyncResult] = []
    total_processed = 0

    # Sync each symbol
    for symbol in symbols:
        result = await sync_price_history(db, symbol, period=period)

        if result.success:
            successful.append(symbol)
            total_processed += result.records_processed
        else:
            failed.append(result)

    # Determine final status
    finished_at = datetime.now(timezone.utc)
    if not failed:
        status = "success"
    elif successful:
        status = "partial"
    else:
        status = "failed"

    # Update PipelineLog
    log.status = status
    log.finished_at = finished_at
    log.processed_count = total_processed
    if failed:
        log.error_message = "; ".join(
            f.error_message for f in failed if f.error_message
        )[:500]  # Truncate to fit column
    log.details = {
        "successful_symbols": successful,
        "failed_symbols": [f.symbol for f in failed],
        "period": period,
        "total_symbols": len(symbols),
    }
    await db.commit()

    duration = (finished_at - started_at).total_seconds()
    logger.info(
        f"Batch sync complete: status={status}, "
        f"processed={total_processed}, duration={duration:.2f}s"
    )

    return BatchSyncResult(
        pipeline_name=pipeline_name,
        run_id=run_id,
        status=status,
        started_at=started_at,
        finished_at=finished_at,
        total_processed=total_processed,
        successful=successful,
        failed=failed,
        details=log.details,
    )


async def get_active_stocks(db: AsyncSession) -> list[str]:
    """
    Get list of active stock symbols from database.

    Useful for batch_sync_prices when you want to sync all stocks.

    Args:
        db: AsyncSession

    Returns:
        List of active stock symbols
    """
    result = await db.execute(
        select(Stock.symbol).where(Stock.is_active == True)
    )
    return [row[0] for row in result.all()]
