"""KAP data ingestion service.

Orchestrates provider fetch + mapper upsert + PipelineLog tracking
for KAP filings data.
"""

import asyncio
import uuid
from datetime import datetime, date, timezone, timedelta
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pipeline_log import PipelineLog
from app.models.stock import Stock
from app.services.data.mappers.kap_report_mapper import upsert_kap_filings
from app.services.data.provider_exceptions import (
    ProviderConnectionError,
    ProviderTimeoutError,
    ProviderRateLimitError,
    ProviderSymbolNotFoundError,
    ProviderDataNotFoundError,
    ProviderAPIError,
)
from app.services.data.provider_registry import get_provider_for_kap_filings
from app.services.data.provider_models import KapFiling
from app.services.utils.logging import logger


# ============================================================================
# Result Models
# ============================================================================


class KapSyncResult(BaseModel):
    """Result of KAP filings sync for a single symbol."""

    symbol: str
    success: bool
    filings_processed: int = 0
    validation_warnings: list[str] = []
    error_message: str | None = None
    duration_seconds: float | None = None


class KapBatchSyncResult(BaseModel):
    """Result of batch KAP filings sync."""

    pipeline_name: str
    run_id: str
    status: str  # "success", "partial", "failed"
    started_at: datetime
    finished_at: datetime
    total_processed: int
    successful: list[str]
    failed: list[KapSyncResult]
    details: dict[str, Any] | None = None


# ============================================================================
# Retry Configuration
# ============================================================================

DEFAULT_RETRY_COUNT = 3
DEFAULT_RETRY_DELAY_BASE = 2  # Exponential backoff: 2^attempt seconds
DEFAULT_DAYS_BACK = 30
DEFAULT_FILING_TYPES = ["FR"]  # Financial Reports by default


# ============================================================================
# Validation Functions
# ============================================================================


def validate_filing_fields(filing: KapFiling) -> list[str]:
    """
    Validate required fields for a KAP filing.

    Args:
        filing: KapFiling to validate

    Returns:
        List of validation warnings (empty if all valid)
    """
    warnings: list[str] = []

    # source_url is required for deduplication
    if filing.source_url is None:
        warnings.append(f"Filing '{filing.title[:50]}' missing source_url")

    # pdf_url is optional but log if missing
    if filing.pdf_url is None:
        warnings.append(f"Filing '{filing.title[:50]}' missing pdf_url")

    return warnings


# ============================================================================
# Service Functions
# ============================================================================


async def sync_kap_filings(
    db: AsyncSession,
    symbol: str,
    filing_types: list[str] | None = None,
    days_back: int = DEFAULT_DAYS_BACK,
    max_retries: int = DEFAULT_RETRY_COUNT,
) -> KapSyncResult:
    """
    Sync KAP filings for a single symbol.

    Flow:
    1. Check stock exists in database
    2. Get provider (default: fallback_kap via registry)
    3. Fetch filings from provider (sync -> async wrapper)
    4. Validate filings (source_url required)
    5. Upsert to database via mapper
    6. Return result with success/failure details

    Args:
        db: AsyncSession
        symbol: Stock symbol (e.g., "THYAO")
        filing_types: List of filing types to fetch (default: ["FR"])
        days_back: Number of days to look back (default: 30)
        max_retries: Maximum retry attempts for transient errors

    Returns:
        KapSyncResult with success status and filing count
    """
    symbol = symbol.upper()
    start_time = datetime.now(timezone.utc)

    # Default filing types if not provided
    if filing_types is None:
        filing_types = DEFAULT_FILING_TYPES

    # Calculate start_date from days_back
    start_date = date.today() - timedelta(days=days_back)

    # Check stock exists
    result = await db.execute(
        select(Stock.id).where(Stock.symbol == symbol)
    )
    stock_id = result.scalar_one_or_none()
    if stock_id is None:
        logger.warning(f"Stock {symbol} not found in database")
        return KapSyncResult(
            symbol=symbol,
            success=False,
            error_message=f"Stock {symbol} not found in database",
        )

    # Get provider
    provider = get_provider_for_kap_filings()

    # Validation warnings accumulator
    all_validation_warnings: list[str] = []

    # Retry loop for transient errors
    attempt = 0
    while attempt < max_retries:
        try:
            logger.info(f"Fetching KAP filings for {symbol} (attempt {attempt + 1})...")

            # Provider is synchronous, wrap with asyncio.to_thread
            filings = await asyncio.to_thread(
                provider.get_kap_filings,
                symbol,
                start_date=start_date,
                filing_types=filing_types,
            )

            # Empty filings is OK
            if not filings:
                logger.info(f"No KAP filings returned for {symbol}")
                duration = (datetime.now(timezone.utc) - start_time).total_seconds()
                return KapSyncResult(
                    symbol=symbol,
                    success=True,
                    filings_processed=0,
                    duration_seconds=duration,
                )

            # Validate filings
            filings_to_upsert: list[KapFiling] = []
            for filing in filings:
                warnings = validate_filing_fields(filing)
                all_validation_warnings.extend(warnings)
                # Only include filings with source_url (required for deduplication)
                if filing.source_url is not None:
                    filings_to_upsert.append(filing)

            # Upsert to database
            count = await upsert_kap_filings(db, symbol, filings_to_upsert)

            # Transform to News entries
            from app.services.news_service import batch_transform_kap_to_news
            news_count = await batch_transform_kap_to_news(db, symbol)
            if news_count > 0:
                logger.info(f"Transformed {news_count} KAP filings to News for {symbol}")

            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            logger.info(f"Synced {count} KAP filings for {symbol} in {duration:.2f}s")

            return KapSyncResult(
                symbol=symbol,
                success=True,
                filings_processed=count,
                validation_warnings=all_validation_warnings,
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
                return KapSyncResult(
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
                return KapSyncResult(
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
            return KapSyncResult(
                symbol=symbol,
                success=False,
                error_message=f"Symbol not found: {e}",
                duration_seconds=duration,
            )

        except ProviderDataNotFoundError as e:
            # Empty data is OK, return success with 0 records
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            logger.info(f"No data found for {symbol}: {e}")
            return KapSyncResult(
                symbol=symbol,
                success=True,
                filings_processed=0,
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
                return KapSyncResult(
                    symbol=symbol,
                    success=False,
                    error_message=f"API error: {e}",
                    duration_seconds=duration,
                )

        except Exception as e:
            # Unexpected error - log and fail
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            logger.error(f"Unexpected error syncing {symbol}: {e}")
            return KapSyncResult(
                symbol=symbol,
                success=False,
                error_message=f"Unexpected error: {e}",
                duration_seconds=duration,
            )

    # Should not reach here
    return KapSyncResult(
        symbol=symbol,
        success=False,
        error_message="Max retries exceeded",
    )


async def batch_sync_kap_filings(
    db: AsyncSession,
    symbols: list[str],
    filing_types: list[str] | None = None,
    days_back: int = DEFAULT_DAYS_BACK,
) -> KapBatchSyncResult:
    """
    Batch sync KAP filings for multiple symbols.

    Flow:
    1. Create PipelineLog entry (run_id = uuid4, status = "running")
    2. Iterate symbols with error handling
    3. Update PipelineLog with results
    4. Return KapBatchSyncResult

    Args:
        db: AsyncSession
        symbols: List of stock symbols
        filing_types: List of filing types to fetch (default: ["FR"])
        days_back: Number of days to look back (default: 30)

    Returns:
        KapBatchSyncResult with overall status and per-symbol results
    """
    run_id = str(uuid.uuid4())
    pipeline_name = "kap_filings_sync"
    started_at = datetime.now(timezone.utc)

    # Default filing types if not provided
    if filing_types is None:
        filing_types = DEFAULT_FILING_TYPES

    logger.info(f"Starting batch KAP sync (run_id={run_id}) for {len(symbols)} symbols")

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
    failed: list[KapSyncResult] = []
    total_processed = 0

    # Sync each symbol
    for symbol in symbols:
        result = await sync_kap_filings(
            db, symbol, filing_types=filing_types, days_back=days_back
        )

        if result.success:
            successful.append(symbol)
            total_processed += result.filings_processed
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
        "filing_types": filing_types,
        "days_back": days_back,
        "total_symbols": len(symbols),
    }
    await db.commit()

    duration = (finished_at - started_at).total_seconds()
    logger.info(
        f"Batch KAP sync complete: status={status}, "
        f"processed={total_processed}, duration={duration:.2f}s"
    )

    return KapBatchSyncResult(
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