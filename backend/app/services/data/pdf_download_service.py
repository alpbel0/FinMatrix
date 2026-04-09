"""PDF Download Service for KAP filings.

This service handles downloading PDF documents from KAP.org.tr and storing them locally.
It does NOT create PipelineLog entries - that is the responsibility of the scheduler wrapper.

Key principles:
- Service functions return Pydantic result objects (no DB logging)
- Scheduler wrapper creates THE ONLY PipelineLog for the run
- Primary retry mechanism is status-based (next scheduled run)
"""

import re
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.kap_report import KapReport
from app.models.stock import Stock
from app.services.utils.logging import logger


# ============================================================================
# Constants
# ============================================================================

PDF_MAGIC_BYTES = b"%PDF-"
MIN_PDF_SIZE = 1024  # 1KB minimum for valid PDF

# Retry-eligible error patterns (for batch_retry_failed_downloads query)
RETRY_ELIGIBLE_PATTERNS = [
    "Timeout",
    "ConnectError",
    "connection refused",
    "HTTP 500",
    "HTTP 502",
    "HTTP 503",
    "Invalid PDF",
]


# ============================================================================
# Enums
# ============================================================================


class PdfDownloadStatus(str, Enum):
    """PDF download status values."""
    PENDING = "PENDING"
    DOWNLOADING = "DOWNLOADING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    NOT_AVAILABLE = "NOT_AVAILABLE"


# ============================================================================
# Pydantic Result Models
# ============================================================================


class PdfDownloadResult(BaseModel):
    """Result of a single PDF download attempt."""
    kap_report_id: int
    symbol: str
    disclosure_index: str | None
    success: bool
    file_size: int | None = None
    local_path: str | None = None
    error_message: str | None = None
    status: PdfDownloadStatus
    duration_ms: int | None = None


class PdfBatchDownloadResult(BaseModel):
    """Result of batch PDF download operation.

    NO run_id field - scheduler wrapper handles PipelineLog.
    """
    total_processed: int
    successful: int
    failed: int
    not_available: int
    status: str  # "success", "partial", "failed"
    results: list[PdfDownloadResult] = []
    details: dict[str, Any] | None = None


# ============================================================================
# Helper Functions
# ============================================================================


def _parse_disclosure_index(pdf_url: str) -> str | None:
    """Extract disclosure index from KAP PDF URL.

    URL format: https://www.kap.org.tr/tr/api/BildirimPdf/{disclosure_index}

    Args:
        pdf_url: The KAP PDF API URL.

    Returns:
        The disclosure index string, or None if parsing fails.
    """
    if not pdf_url:
        return None

    match = re.match(
        r"^https?://www\.kap\.org\.tr/tr/api/BildirimPdf/(\d+)/?$",
        pdf_url,
    )
    if not match:
        return None
    return match.group(1)


def _build_local_path(
    symbol: str,
    disclosure_index: str,
    published_at: datetime | None,
    storage_base: Path,
) -> Path:
    """Construct local file path for PDF storage.

    Path format: {storage_base}/{symbol}/{year}/{disclosure_index}.pdf

    Args:
        symbol: Stock symbol (e.g., "THYAO").
        disclosure_index: KAP disclosure index.
        published_at: Publication date (for year directory).
        storage_base: Base storage directory path.

    Returns:
        Full Path object for the PDF file.
    """
    year = published_at.year if published_at else datetime.now(timezone.utc).year
    return storage_base / symbol.upper() / str(year) / f"{disclosure_index}.pdf"


def _validate_pdf_content(content: bytes) -> bool:
    """Validate that downloaded content is a valid PDF.

    Checks:
    - Magic bytes: PDF files start with "%PDF-"
    - Minimum size: at least 1KB

    Args:
        content: The downloaded file content.

    Returns:
        True if valid PDF, False otherwise.
    """
    if len(content) < MIN_PDF_SIZE:
        return False
    return content[:5] == PDF_MAGIC_BYTES


def _classify_error(error: Exception) -> tuple[PdfDownloadStatus, str]:
    """Classify download error and determine appropriate status.

    Args:
        error: The exception that occurred during download.

    Returns:
        Tuple of (status, error_message) for database storage.
    """
    error_message = str(error)

    if isinstance(error, httpx.HTTPStatusError):
        if error.response.status_code == 404:
            return PdfDownloadStatus.NOT_AVAILABLE, f"HTTP 404: PDF not found"
        if error.response.status_code in (500, 502, 503):
            return PdfDownloadStatus.FAILED, f"HTTP {error.response.status_code}: KAP server error"
        return PdfDownloadStatus.FAILED, f"HTTP {error.response.status_code}: {error_message}"

    if isinstance(error, httpx.TimeoutException):
        return PdfDownloadStatus.FAILED, f"Timeout: Request timed out after {get_settings().pdf_download_timeout}s"

    if isinstance(error, httpx.ConnectError):
        return PdfDownloadStatus.FAILED, f"ConnectError: {error_message}"

    if isinstance(error, OSError):
        # Disk write errors - NOT retry eligible
        return PdfDownloadStatus.FAILED, f"OSError: {error_message}"

    if isinstance(error, ValueError):
        # Invalid URL - permanent failure
        return PdfDownloadStatus.NOT_AVAILABLE, f"Invalid URL: {error_message}"

    # Generic error
    return PdfDownloadStatus.FAILED, error_message


def _is_retry_eligible(error_message: str) -> bool:
    """Check if error is eligible for retry in next scheduled run.

    Args:
        error_message: The error message stored in pdf_download_error.

    Returns:
        True if the error is retry-eligible, False otherwise.
    """
    return any(pattern in error_message for pattern in RETRY_ELIGIBLE_PATTERNS)


# ============================================================================
# Core Service Functions
# ============================================================================


async def download_single_pdf(
    db: AsyncSession,
    kap_report: KapReport,
    storage_base: Path,
    timeout: float | None = None,
) -> PdfDownloadResult:
    """Download a single PDF file from KAP.org.tr.

    This function:
    - Parses the disclosure index from pdf_url
    - Downloads the PDF via httpx AsyncClient
    - Validates the PDF content
    - Updates KapReport fields (DB commit)
    - Returns PdfDownloadResult (NO PipelineLog creation)

    Within-run transient retry:
    - Only for timeout/connection errors
    - Max retries defined by pdf_transient_retry_count config
    - Does NOT retry for 404, disk errors, etc.

    Args:
        db: AsyncSession for database operations.
        kap_report: The KapReport to download PDF for.
        storage_base: Base directory for PDF storage.
        timeout: Download timeout in seconds.

    Returns:
        PdfDownloadResult with download outcome.
    """
    settings = get_settings()
    timeout = timeout or settings.pdf_download_timeout
    max_retries = settings.pdf_transient_retry_count
    start_time = datetime.now(timezone.utc)

    # Parse disclosure index
    disclosure_index = _parse_disclosure_index(kap_report.pdf_url or "")
    if not disclosure_index:
        # Update status and return
        kap_report.pdf_download_status = PdfDownloadStatus.NOT_AVAILABLE.value
        kap_report.pdf_download_error = "Invalid URL: Could not parse disclosure index"
        await db.commit()
        return PdfDownloadResult(
            kap_report_id=kap_report.id,
            symbol="",  # Will be populated by caller
            disclosure_index=None,
            success=False,
            status=PdfDownloadStatus.NOT_AVAILABLE,
            error_message="Invalid URL: Could not parse disclosure index",
        )

    # Resolve symbol from related stock or fallback DB lookup.
    symbol = ""
    stock = getattr(kap_report, "stock", None)
    if stock and stock.symbol:
        symbol = stock.symbol
    elif kap_report.stock_id is not None:
        stock_result = await db.execute(
            select(Stock.symbol).where(Stock.id == kap_report.stock_id)
        )
        symbol = stock_result.scalar_one_or_none() or ""

    if not symbol:
        kap_report.pdf_download_status = PdfDownloadStatus.NOT_AVAILABLE.value
        kap_report.pdf_download_error = "Invalid stock reference: Could not resolve symbol"
        await db.commit()
        duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
        return PdfDownloadResult(
            kap_report_id=kap_report.id,
            symbol="",
            disclosure_index=disclosure_index,
            success=False,
            status=PdfDownloadStatus.NOT_AVAILABLE,
            error_message="Invalid stock reference: Could not resolve symbol",
            duration_ms=duration_ms,
        )

    # Build local path
    local_path = _build_local_path(
        symbol=symbol,
        disclosure_index=disclosure_index,
        published_at=kap_report.published_at,
        storage_base=storage_base,
    )

    # Set status to DOWNLOADING
    kap_report.pdf_download_status = PdfDownloadStatus.DOWNLOADING.value
    await db.commit()

    # Download with transient retry
    pdf_content: bytes | None = None
    last_error: Exception | None = None
    retry_count = 0

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        while retry_count <= max_retries:
            try:
                response = await client.get(kap_report.pdf_url)
                response.raise_for_status()
                pdf_content = response.content
                break  # Success, exit retry loop
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                # Transient network error - retry
                last_error = e
                retry_count += 1
                if retry_count <= max_retries:
                    logger.warning(
                        f"Transient error downloading PDF {disclosure_index}, "
                        f"retry {retry_count}/{max_retries}: {e}"
                    )
            except Exception as e:
                # Non-retry error - exit immediately
                last_error = e
                break

    # Check if download succeeded
    if pdf_content is None:
        # Download failed
        status, error_message = _classify_error(last_error or Exception("Unknown error"))
        kap_report.pdf_download_status = status.value
        kap_report.pdf_download_error = error_message
        await db.commit()

        duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
        return PdfDownloadResult(
            kap_report_id=kap_report.id,
            symbol=symbol,
            disclosure_index=disclosure_index,
            success=False,
            status=status,
            error_message=error_message,
            duration_ms=duration_ms,
        )

    # Validate PDF content
    if not _validate_pdf_content(pdf_content):
        kap_report.pdf_download_status = PdfDownloadStatus.FAILED.value
        kap_report.pdf_download_error = "Invalid PDF: Content validation failed (not a valid PDF or too small)"
        await db.commit()

        duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
        return PdfDownloadResult(
            kap_report_id=kap_report.id,
            symbol=symbol,
            disclosure_index=disclosure_index,
            success=False,
            status=PdfDownloadStatus.FAILED,
            error_message="Invalid PDF: Content validation failed",
            duration_ms=duration_ms,
        )

    # Write to disk
    try:
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(pdf_content)
    except OSError as e:
        # Disk write error - NOT retry eligible
        kap_report.pdf_download_status = PdfDownloadStatus.FAILED.value
        kap_report.pdf_download_error = f"OSError: {e}"
        await db.commit()

        duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
        return PdfDownloadResult(
            kap_report_id=kap_report.id,
            symbol=symbol,
            disclosure_index=disclosure_index,
            success=False,
            status=PdfDownloadStatus.FAILED,
            error_message=f"OSError: {e}",
            duration_ms=duration_ms,
        )

    # Success - update KapReport
    file_size = len(pdf_content)
    relative_path = f"{symbol}/{local_path.parent.name}/{disclosure_index}.pdf"

    kap_report.local_pdf_path = relative_path
    kap_report.pdf_download_status = PdfDownloadStatus.COMPLETED.value
    kap_report.pdf_file_size = file_size
    kap_report.pdf_downloaded_at = datetime.now(timezone.utc)
    kap_report.pdf_download_error = None
    await db.commit()

    duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
    return PdfDownloadResult(
        kap_report_id=kap_report.id,
        symbol=symbol,
        disclosure_index=disclosure_index,
        success=True,
        file_size=file_size,
        local_path=relative_path,
        status=PdfDownloadStatus.COMPLETED,
        duration_ms=duration_ms,
    )


async def batch_download_pending_pdfs(
    db: AsyncSession,
    limit: int = 50,
    filing_types: list[str] | None = None,
) -> PdfBatchDownloadResult:
    """Download all pending PDFs.

    Query KapReports where pdf_download_status='PENDING' and pdf_url IS NOT NULL.
    Does NOT create PipelineLog - returns result only.

    Args:
        db: AsyncSession for database operations.
        limit: Maximum number of PDFs to download.
        filing_types: Filter by filing types (e.g., ["FR"]). None = all types.

    Returns:
        PdfBatchDownloadResult with batch outcome.
    """
    settings = get_settings()
    storage_base = Path(settings.pdf_storage_path)

    # Build query
    query = (
        select(KapReport)
        .where(
            KapReport.pdf_download_status == PdfDownloadStatus.PENDING.value,
            KapReport.pdf_url.isnot(None),
        )
        .order_by(KapReport.published_at.desc())
        .limit(limit)
    )

    # Apply filing type filter if specified
    if filing_types:
        query = query.where(KapReport.filing_type.in_(filing_types))

    result = await db.execute(query)
    kap_reports = result.scalars().all()

    if not kap_reports:
        return PdfBatchDownloadResult(
            total_processed=0,
            successful=0,
            failed=0,
            not_available=0,
            status="success",
            results=[],
        )

    # Download each PDF
    results: list[PdfDownloadResult] = []
    successful = 0
    failed = 0
    not_available = 0

    for kap_report in kap_reports:
        download_result = await download_single_pdf(
            db=db,
            kap_report=kap_report,
            storage_base=storage_base,
        )
        results.append(download_result)

        if download_result.success:
            successful += 1
        elif download_result.status == PdfDownloadStatus.NOT_AVAILABLE:
            not_available += 1
        else:
            failed += 1

    # Determine batch status
    if failed == 0 and not_available == 0:
        batch_status = "success"
    elif successful > 0:
        batch_status = "partial"
    else:
        batch_status = "failed"

    return PdfBatchDownloadResult(
        total_processed=len(kap_reports),
        successful=successful,
        failed=failed,
        not_available=not_available,
        status=batch_status,
        results=results,
    )


async def batch_retry_failed_downloads(
    db: AsyncSession,
    limit: int = 50,
) -> PdfBatchDownloadResult:
    """Retry failed PDF downloads that are eligible for retry.

    Query KapReports where pdf_download_status='FAILED' AND error is retry-eligible.
    Does NOT create PipelineLog - returns result only.

    Retry-eligible errors:
    - Timeout
    - ConnectError / connection refused
    - HTTP 500/502/503
    - Invalid PDF (may have been corrupted during download)

    NOT retry-eligible:
    - OSError (disk write errors)
    - HTTP 404 (PDF not available)
    - Invalid URL

    Args:
        db: AsyncSession for database operations.
        limit: Maximum number of PDFs to retry.

    Returns:
        PdfBatchDownloadResult with retry outcome.
    """
    settings = get_settings()
    storage_base = Path(settings.pdf_storage_path)

    # Build query with retry-eligible error patterns
    retry_conditions = [
        KapReport.pdf_download_error.contains(pattern)
        for pattern in RETRY_ELIGIBLE_PATTERNS
    ]

    query = (
        select(KapReport)
        .where(
            KapReport.pdf_download_status == PdfDownloadStatus.FAILED.value,
            or_(*retry_conditions),
        )
        .order_by(KapReport.published_at.desc())
        .limit(limit)
    )

    result = await db.execute(query)
    kap_reports = result.scalars().all()

    if not kap_reports:
        return PdfBatchDownloadResult(
            total_processed=0,
            successful=0,
            failed=0,
            not_available=0,
            status="success",
            results=[],
        )

    results: list[PdfDownloadResult] = []
    successful = 0
    failed = 0
    not_available = 0

    for kap_report in kap_reports:
        kap_report.pdf_download_status = PdfDownloadStatus.PENDING.value
        await db.commit()

        download_result = await download_single_pdf(
            db=db,
            kap_report=kap_report,
            storage_base=storage_base,
        )
        results.append(download_result)

        if download_result.success:
            successful += 1
        elif download_result.status == PdfDownloadStatus.NOT_AVAILABLE:
            not_available += 1
        else:
            failed += 1

    if failed == 0 and not_available == 0:
        batch_status = "success"
    elif successful > 0:
        batch_status = "partial"
    else:
        batch_status = "failed"

    return PdfBatchDownloadResult(
        total_processed=len(kap_reports),
        successful=successful,
        failed=failed,
        not_available=not_available,
        status=batch_status,
        results=results,
    )


async def get_download_statistics(db: AsyncSession) -> dict[str, int]:
    """Get PDF download statistics by status.

    Args:
        db: AsyncSession for database operations.

    Returns:
        Dictionary with counts for each status.
    """
    from sqlalchemy import func

    query = (
        select(
            KapReport.pdf_download_status,
            func.count(KapReport.id).label("count"),
        )
        .group_by(KapReport.pdf_download_status)
    )

    result = await db.execute(query)
    rows = result.all()

    stats = {status.value: 0 for status in PdfDownloadStatus}
    for row in rows:
        if row.pdf_download_status:
            stats[row.pdf_download_status] = row.count

    return stats
