"""Financial statements ingestion service.

Orchestrates provider fetch + mapper upsert + validation
for income statements, balance sheets, and cash flows.
"""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, Sequence

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pipeline_log import PipelineLog
from app.models.stock import Stock
from app.services.data.mappers.financials_mapper import upsert_financial_statement_set
from app.services.data.provider_exceptions import (
    ProviderConnectionError,
    ProviderTimeoutError,
    ProviderRateLimitError,
    ProviderSymbolNotFoundError,
    ProviderDataNotFoundError,
    ProviderAPIError,
)
from app.services.data.provider_registry import get_provider_for_financials
from app.services.data.provider_models import (
    FinancialStatementSet,
    PeriodType,
)
from app.services.utils.logging import logger


# ============================================================================
# Result Models
# ============================================================================


class FinancialSyncResult(BaseModel):
    """Result of a financial statements sync for a single symbol."""

    symbol: str
    success: bool
    annual_count: int = 0
    quarterly_count: int = 0
    total_statements: int = 0
    validation_warnings: list[str] = []
    error_message: str | None = None
    duration_seconds: float | None = None


class FinancialBatchSyncResult(BaseModel):
    """Result of a batch financial sync operation."""

    pipeline_name: str
    run_id: str
    status: str  # "success", "partial", "failed"
    started_at: datetime
    finished_at: datetime
    total_statements: int
    successful: list[str]
    failed: list[FinancialSyncResult]
    details: dict[str, Any] | None = None


# ============================================================================
# Validation Functions
# ============================================================================


def validate_quarterly_net_income(
    statements: Sequence[FinancialStatementSet],
    required_count: int = 8,
) -> list[str]:
    """
    Validate that last N quarters have net income data.

    ROADMAP Task 4.2 requirement: "Son 8 çeyreklik net kar verisini doğrula"

    Args:
        statements: List of quarterly financial statements (sorted by date desc)
        required_count: Minimum required quarters with net_income

    Returns:
        List of validation warning messages (empty if all valid)
    """
    warnings: list[str] = []

    # Check count
    if len(statements) < required_count:
        warnings.append(
            f"Only {len(statements)} quarters available, expected {required_count}"
        )

    # Check net_income presence for required quarters
    missing_dates = []
    for stmt in statements[:required_count]:
        if stmt.net_income is None:
            missing_dates.append(str(stmt.statement_date))

    if missing_dates:
        warnings.append(f"Missing net_income for dates: {', '.join(missing_dates)}")

    return warnings


# ============================================================================
# Retry Configuration
# ============================================================================

DEFAULT_RETRY_COUNT = 3
DEFAULT_RETRY_DELAY_BASE = 2


# ============================================================================
# Service Functions
# ============================================================================


async def sync_financial_statements(
    db: AsyncSession,
    symbol: str,
    period_type: PeriodType = PeriodType.ANNUAL,
    last_n: int = 5,
    validate_quarterly: bool = True,
) -> FinancialSyncResult:
    """
    Sync financial statements for a single symbol.

    Flow:
    1. Check stock exists in database
    2. Get provider (default: borsapy)
    3. Fetch financial statements from provider
    4. Validate quarterly net_income (if quarterly and validate_quarterly=True)
    5. Upsert each statement via mapper
    6. Return result with counts and warnings

    Args:
        db: AsyncSession
        symbol: Stock symbol (e.g., "THYAO")
        period_type: ANNUAL or QUARTERLY
        last_n: Number of periods to fetch
        validate_quarterly: Whether to validate last 8 quarters have net_income

    Returns:
        FinancialSyncResult with counts and validation warnings
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
        return FinancialSyncResult(
            symbol=symbol,
            success=False,
            error_message=f"Stock {symbol} not found in database",
        )

    # Get provider
    provider = get_provider_for_financials()

    # Retry loop. `attempt` counts only retry-consuming failures.
    attempt = 0
    while attempt < DEFAULT_RETRY_COUNT:
        try:
            logger.info(
                f"Fetching financial statements for {symbol} "
                f"(period={period_type.value}, last_n={last_n}, attempt={attempt + 1})..."
            )

            # Provider is synchronous, wrap with asyncio.to_thread
            statements = await asyncio.to_thread(
                provider.get_financial_statements,
                symbol,
                period_type=period_type,
                last_n=last_n,
            )

            # Empty data is OK
            if not statements:
                duration = (datetime.now(timezone.utc) - start_time).total_seconds()
                logger.info(f"No financial statements returned for {symbol}")
                return FinancialSyncResult(
                    symbol=symbol,
                    success=True,
                    annual_count=0 if period_type == PeriodType.ANNUAL else 0,
                    quarterly_count=0 if period_type == PeriodType.QUARTERLY else 0,
                    total_statements=0,
                    duration_seconds=duration,
                )

            # Validate quarterly net_income if requested
            validation_warnings = []
            if period_type == PeriodType.QUARTERLY and validate_quarterly:
                validation_warnings = validate_quarterly_net_income(
                    statements, required_count=8
                )
                if validation_warnings:
                    logger.warning(
                        f"Quarterly validation warnings for {symbol}: {validation_warnings}"
                    )

            # Upsert each statement
            total_processed = 0
            failed_upserts: list[str] = []
            for stmt in statements:
                try:
                    result_dict = await upsert_financial_statement_set(db, symbol, stmt)
                    # result_dict: {"balance_sheet": bool, "income_statement": bool, "cash_flow": bool}
                    if all(result_dict.values()):
                        total_processed += 1
                    else:
                        failed_tables = [name for name, saved in result_dict.items() if not saved]
                        failed_upserts.append(
                            f"{stmt.statement_date}: missing {', '.join(failed_tables)}"
                        )
                except Exception as e:
                    logger.error(f"Failed to upsert statement for {stmt.statement_date}: {e}")
                    failed_upserts.append(f"{stmt.statement_date}: {e}")

            if failed_upserts:
                duration = (datetime.now(timezone.utc) - start_time).total_seconds()
                return FinancialSyncResult(
                    symbol=symbol,
                    success=False,
                    annual_count=total_processed if period_type == PeriodType.ANNUAL else 0,
                    quarterly_count=total_processed if period_type == PeriodType.QUARTERLY else 0,
                    total_statements=total_processed,
                    validation_warnings=validation_warnings,
                    error_message=f"Failed to persist statements: {'; '.join(failed_upserts[:5])}",
                    duration_seconds=duration,
                )

            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            logger.info(
                f"Synced {total_processed} financial statements for {symbol} "
                f"in {duration:.2f}s"
            )

            return FinancialSyncResult(
                symbol=symbol,
                success=True,
                annual_count=total_processed if period_type == PeriodType.ANNUAL else 0,
                quarterly_count=total_processed if period_type == PeriodType.QUARTERLY else 0,
                total_statements=total_processed,
                validation_warnings=validation_warnings,
                duration_seconds=duration,
            )

        except ProviderConnectionError as e:
            attempt += 1
            if attempt < DEFAULT_RETRY_COUNT:
                delay = DEFAULT_RETRY_DELAY_BASE ** (attempt - 1)
                logger.warning(
                    f"Connection error for {symbol}, retrying in {delay}s "
                    f"(attempt {attempt + 1}/{DEFAULT_RETRY_COUNT})"
                )
                await asyncio.sleep(delay)
            else:
                duration = (datetime.now(timezone.utc) - start_time).total_seconds()
                logger.error(f"Failed to sync {symbol} after {DEFAULT_RETRY_COUNT} attempts")
                return FinancialSyncResult(
                    symbol=symbol,
                    success=False,
                    error_message=f"Connection error: {e}",
                    duration_seconds=duration,
                )

        except ProviderTimeoutError as e:
            attempt += 1
            if attempt < DEFAULT_RETRY_COUNT:
                delay = DEFAULT_RETRY_DELAY_BASE ** (attempt - 1)
                await asyncio.sleep(delay)
            else:
                duration = (datetime.now(timezone.utc) - start_time).total_seconds()
                return FinancialSyncResult(
                    symbol=symbol,
                    success=False,
                    error_message=f"Timeout: {e}",
                    duration_seconds=duration,
                )

        except ProviderRateLimitError as e:
            retry_after = getattr(e, 'retry_after', 60)
            logger.warning(f"Rate limited for {symbol}, waiting {retry_after}s")
            await asyncio.sleep(retry_after)
            continue

        except ProviderSymbolNotFoundError as e:
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            logger.warning(f"Symbol {symbol} not found by provider")
            return FinancialSyncResult(
                symbol=symbol,
                success=False,
                error_message=f"Symbol not found: {e}",
                duration_seconds=duration,
            )

        except ProviderDataNotFoundError as e:
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            return FinancialSyncResult(
                symbol=symbol,
                success=True,  # Empty data is OK
                total_statements=0,
                duration_seconds=duration,
            )

        except ProviderAPIError as e:
            status_code = getattr(e, 'status_code', None)
            if status_code and status_code >= 500:
                attempt += 1
            if status_code and status_code >= 500 and attempt < DEFAULT_RETRY_COUNT:
                delay = DEFAULT_RETRY_DELAY_BASE ** (attempt - 1)
                await asyncio.sleep(delay)
            else:
                duration = (datetime.now(timezone.utc) - start_time).total_seconds()
                return FinancialSyncResult(
                    symbol=symbol,
                    success=False,
                    error_message=f"API error: {e}",
                    duration_seconds=duration,
                )

        except Exception as e:
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            logger.error(f"Unexpected error syncing financials for {symbol}: {e}")
            return FinancialSyncResult(
                symbol=symbol,
                success=False,
                error_message=f"Unexpected error: {e}",
                duration_seconds=duration,
            )

    return FinancialSyncResult(
        symbol=symbol,
        success=False,
        error_message="Max retries exceeded",
    )


async def sync_all_financial_statements(
    db: AsyncSession,
    symbol: str,
    annual_last_n: int = 5,
    quarterly_last_n: int = 8,
    validate_quarterly: bool = True,
) -> FinancialSyncResult:
    """
    Sync both annual and quarterly financial statements.

    Convenience function that calls sync_financial_statements twice
    and aggregates results.

    Args:
        db: AsyncSession
        symbol: Stock symbol
        annual_last_n: Number of annual periods to fetch
        quarterly_last_n: Number of quarterly periods to fetch
        validate_quarterly: Whether to validate quarterly net_income

    Returns:
        FinancialSyncResult with aggregated counts
    """
    symbol = symbol.upper()
    start_time = datetime.now(timezone.utc)

    # Sync annual
    annual_result = await sync_financial_statements(
        db, symbol,
        period_type=PeriodType.ANNUAL,
        last_n=annual_last_n,
        validate_quarterly=False,
    )

    # Sync quarterly
    quarterly_result = await sync_financial_statements(
        db, symbol,
        period_type=PeriodType.QUARTERLY,
        last_n=quarterly_last_n,
        validate_quarterly=validate_quarterly,
    )

    duration = (datetime.now(timezone.utc) - start_time).total_seconds()

    # Aggregate results
    success = annual_result.success and quarterly_result.success
    total = annual_result.total_statements + quarterly_result.total_statements

    warnings = quarterly_result.validation_warnings

    error_message = None
    if annual_result.error_message or quarterly_result.error_message:
        errors = []
        if annual_result.error_message:
            errors.append(f"Annual: {annual_result.error_message}")
        if quarterly_result.error_message:
            errors.append(f"Quarterly: {quarterly_result.error_message}")
        error_message = "; ".join(errors)

    return FinancialSyncResult(
        symbol=symbol,
        success=success,
        annual_count=annual_result.total_statements,
        quarterly_count=quarterly_result.total_statements,
        total_statements=total,
        validation_warnings=warnings,
        error_message=error_message,
        duration_seconds=duration,
    )


async def batch_sync_financials(
    db: AsyncSession,
    symbols: list[str],
    period_type: PeriodType = PeriodType.ANNUAL,
    last_n: int = 5,
    validate_quarterly: bool = True,
) -> FinancialBatchSyncResult:
    """
    Batch sync financial statements for multiple symbols.

    Flow:
    1. Create PipelineLog entry
    2. Iterate symbols with error handling
    3. Update PipelineLog with results
    4. Return BatchSyncResult

    Args:
        db: AsyncSession
        symbols: List of stock symbols
        period_type: ANNUAL or QUARTERLY
        last_n: Number of periods to fetch
        validate_quarterly: Whether to validate quarterly net_income

    Returns:
        FinancialBatchSyncResult with overall status
    """
    run_id = str(uuid.uuid4())
    pipeline_name = "financials_sync"
    started_at = datetime.now(timezone.utc)

    logger.info(
        f"Starting batch financials sync (run_id={run_id}) "
        f"for {len(symbols)} symbols"
    )

    # Create initial PipelineLog
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
    failed: list[FinancialSyncResult] = []
    total_statements = 0

    for symbol in symbols:
        result = await sync_financial_statements(
            db, symbol,
            period_type=period_type,
            last_n=last_n,
            validate_quarterly=validate_quarterly,
        )

        if result.success:
            successful.append(symbol)
            total_statements += result.total_statements
        else:
            failed.append(result)

    # Determine status
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
    log.processed_count = total_statements
    if failed:
        log.error_message = "; ".join(
            f.error_message for f in failed if f.error_message
        )[:500]
    log.details = {
        "successful_symbols": successful,
        "failed_symbols": [f.symbol for f in failed],
        "period_type": period_type.value,
        "last_n": last_n,
        "total_symbols": len(symbols),
    }
    await db.commit()

    duration = (finished_at - started_at).total_seconds()
    logger.info(
        f"Batch financials sync complete: status={status}, "
        f"statements={total_statements}, duration={duration:.2f}s"
    )

    return FinancialBatchSyncResult(
        pipeline_name=pipeline_name,
        run_id=run_id,
        status=status,
        started_at=started_at,
        finished_at=finished_at,
        total_statements=total_statements,
        successful=successful,
        failed=failed,
        details=log.details,
    )
