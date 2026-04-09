"""PDF Chunking Service for KAP filings.

This service handles extracting text from PDF documents and splitting them into
semantic chunks for embedding and retrieval.

Key principles:
- Service functions return Pydantic result objects (no DB logging)
- Scheduler wrapper creates THE ONLY PipelineLog for the run
- Primary retry mechanism is status-based (next scheduled run)
- Empty PDFs are marked COMPLETED with chunking_error for visibility
"""

import hashlib
import re
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

import pdfplumber
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.document_chunk import DocumentChunk
from app.models.kap_report import KapReport
from app.models.stock import Stock
from app.services.utils.logging import logger


# ============================================================================
# Constants
# ============================================================================

CHARS_PER_TOKEN = 4  # Approximate: 1 token ≈ 4 chars for Turkish text
MIN_CHUNK_CHARS = 50  # Minimum meaningful chunk size

# Boilerplate patterns to filter out
BOILERPLATE_PATTERNS = [
    r"^\d{4}\s+Yıl\s+Faaliyet\s+Raporu",  # Cover page: "2024 Yıl Faaliyet Raporu"
    r"^Yıllık\s+Rapor",  # Annual report cover
    r"^İçindekiler",  # Table of contents
    r"^Contents",  # Table of contents (English)
    r"^içindekiler\s+listesi",  # Table of contents variant
    r"^Sayfa\s+\d+$",  # Page numbers: "Sayfa 5"
    r"^Page\s+\d+$",  # Page numbers (English)
]

# Corporate header patterns (short repetitive headers)
CORPORATE_HEADER_PATTERNS = [
    r"^Şirket\s+Adı\s*:?\s*$",
    r"^Company\s+Name\s*:?\s*$",
    r"^Ticker\s*:?\s*$",
    r"^BIST\s*:?\s*$",
    r"^Borsa\s+İstanbul\s*$",
]

FINANCIAL_REPORT_EXPECTED_PATTERNS = [
    r"finansal rapor",
    r"finansal durum tablosu",
    r"gelir tablosu",
    r"nakit akış",
    r"özkaynak",
    r"dipnot",
    r"bağımsız denet",
    r"konsolide",
]

FINANCIAL_REPORT_MISMATCH_PATTERNS = [
    r"kap'ta yayınlanma tarihi ve saati",
    r"ortaklık paylarının",
    r"net aktif değerinin",
    r"özel durum açıklaması",
    r"sermaye artırımı",
    r"geri alım programı",
]


# ============================================================================
# Enums
# ============================================================================


class ChunkingStatus(str, Enum):
    """Chunking status values."""
    PENDING = "PENDING"
    CHUNKING = "CHUNKING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# ============================================================================
# Pydantic Result Models
# ============================================================================


class ChunkingResult(BaseModel):
    """Result of chunking a single PDF."""
    kap_report_id: int
    symbol: str
    disclosure_index: str | None
    success: bool
    chunks_created: int = 0
    chunks_skipped: int = 0  # Duplicate chunks within same PDF or DB
    error_message: str | None = None
    status: ChunkingStatus
    duration_ms: int | None = None


class ChunkingBatchResult(BaseModel):
    """Result of batch chunking operation.

    NO run_id field - scheduler wrapper handles PipelineLog.
    """
    total_processed: int
    successful: int
    failed: int
    status: str  # "success", "partial", "failed"
    results: list[ChunkingResult] = []
    details: dict[str, Any] | None = None


# ============================================================================
# Helper Functions
# ============================================================================


def _compute_chunk_hash(text: str) -> str:
    """Compute SHA-256 hash of normalized chunk text.

    Args:
        text: The chunk text to hash.

    Returns:
        Hexadecimal hash string (64 chars).
    """
    normalized = text.strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _estimate_tokens(text: str) -> int:
    """Estimate token count from character count.

    Uses simple heuristic: 1 token ≈ 4 chars for Turkish text.

    Args:
        text: The text to estimate tokens for.

    Returns:
        Estimated token count.
    """
    return len(text) // CHARS_PER_TOKEN


def _normalize_text(text: str) -> str:
    """Normalize extracted text.

    Operations:
    - Collapse multiple whitespaces to single space
    - Strip leading/trailing whitespace
    - Preserve Turkish characters (no encoding changes)

    Args:
        text: Raw extracted text.

    Returns:
        Normalized text.
    """
    # Collapse multiple whitespace (including newlines) to single space
    text = re.sub(r"\s+", " ", text)
    # Strip leading/trailing whitespace
    text = text.strip()
    return text


def _calculate_alpha_ratio(text: str) -> float:
    """Calculate alphanumeric character ratio.

    Args:
        text: The text to analyze.

    Returns:
        Ratio of alphanumeric chars to total chars (0.0 to 1.0).
    """
    if not text:
        return 0.0

    # Count alphanumeric characters (including Turkish letters)
    alnum_count = sum(1 for c in text if c.isalnum())
    total_count = len(text)

    return alnum_count / total_count if total_count > 0 else 0.0


def _is_boilerplate(text: str) -> bool:
    """Check if text is boilerplate/noise content.

    Boilerplate detection rules:
    1. Very short blocks (< MIN_CHUNK_CHARS)
    2. Table of contents patterns
    3. Cover page patterns
    4. Corporate headers (short repetitive)
    5. Low alphanumeric density (< 0.3)
    6. Page numbers

    Args:
        text: The text block to check.

    Returns:
        True if text is boilerplate, False otherwise.
    """
    settings = get_settings()
    min_chars = settings.min_chunk_chars
    min_alpha = settings.min_alpha_ratio

    # Rule 1: Very short blocks
    if len(text.strip()) < min_chars:
        return True

    # Check patterns
    text_stripped = text.strip()

    # Rule 2-4: Boilerplate patterns
    for pattern in BOILERPLATE_PATTERNS:
        if re.search(pattern, text_stripped, re.IGNORECASE):
            # Check if it's the entire content (or most of it)
            match = re.search(pattern, text_stripped, re.IGNORECASE)
            if match and len(text_stripped) < 200:  # Short boilerplate block
                return True

    # Rule 4: Corporate headers
    for pattern in CORPORATE_HEADER_PATTERNS:
        if re.match(pattern, text_stripped, re.IGNORECASE):
            return True

    # Rule 5: Low alphanumeric density
    alpha_ratio = _calculate_alpha_ratio(text_stripped)
    if alpha_ratio < min_alpha:
        return True

    return False


def _find_duplicate_paragraphs(pages: list[str]) -> set[int]:
    """Find duplicate paragraph indices within a document.

    Args:
        pages: List of page texts.

    Returns:
        Set of paragraph indices that are duplicates (to be filtered).
    """
    seen_hashes: dict[str, int] = {}  # hash -> first paragraph index
    duplicate_indices: set[int] = set()

    paragraph_index = 0
    for page_text in pages:
        # Split page into paragraphs (double newline)
        paragraphs = re.split(r"\n\s*\n", page_text)
        for para in paragraphs:
            para_normalized = _normalize_text(para)
            if not para_normalized:
                continue

            para_hash = _compute_chunk_hash(para_normalized)

            if para_hash in seen_hashes:
                # This paragraph is a duplicate
                duplicate_indices.add(paragraph_index)
            else:
                seen_hashes[para_hash] = paragraph_index

            paragraph_index += 1

    return duplicate_indices


def _detect_content_validation_warning(
    *,
    title: str | None,
    filing_type: str | None,
    chunks: list[str],
) -> str | None:
    """Detect likely content/metadata mismatch for financial reports."""
    if not chunks:
        return None

    title_normalized = (title or "").lower()
    filing_type_normalized = (filing_type or "").upper()
    first_chunk = chunks[0].lower()

    is_financial_report = (
        filing_type_normalized == "FR"
        or "finansal rapor" in title_normalized
        or "financial report" in title_normalized
    )
    if not is_financial_report:
        return None

    has_expected_finance_signal = any(
        re.search(pattern, first_chunk, re.IGNORECASE)
        for pattern in FINANCIAL_REPORT_EXPECTED_PATTERNS
    )
    has_mismatch_signal = any(
        re.search(pattern, first_chunk, re.IGNORECASE)
        for pattern in FINANCIAL_REPORT_MISMATCH_PATTERNS
    )

    if has_mismatch_signal and not has_expected_finance_signal:
        return "content_validation_warning:possible_pdf_metadata_mismatch"
    return None


def _extract_text_from_pdf(pdf_path: Path, max_retries: int = 2) -> list[str]:
    """Extract text from PDF file using pdfplumber.

    Args:
        pdf_path: Path to the PDF file.
        max_retries: Maximum number of retry attempts for transient errors.

    Returns:
        List of page texts (one string per page).

    Raises:
        FileNotFoundError: If PDF file doesn't exist.
        pdfplumber.PDFSyntaxError: If PDF is corrupted (after retries).
        Exception: Other extraction errors.
    """
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    pages: list[str] = []
    retry_count = 0
    last_error: Exception | None = None

    while retry_count <= max_retries:
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text() or ""
                    pages.append(text)
                break  # Success, exit retry loop

        except (pdfplumber.PDFSyntaxError, OSError) as e:
            # Transient error - retry
            last_error = e
            retry_count += 1
            if retry_count <= max_retries:
                logger.warning(
                    f"Transient error extracting PDF {pdf_path.name}, "
                    f"retry {retry_count}/{max_retries}: {e}"
                )

    if not pages and last_error:
        # All retries failed
        raise last_error

    return pages


def _chunk_paragraphs(
    pages: list[str],
    target_tokens: int = 500,
    overlap_tokens: int = 50,
    duplicate_indices: set[int] | None = None,
) -> list[str]:
    """Split pages into chunks based on paragraph boundaries.

    Strategy:
    1. Split pages into paragraphs
    2. Filter out boilerplate paragraphs
    3. Merge paragraphs until reaching target_tokens
    4. Add overlap from previous chunk

    Args:
        pages: List of page texts.
        target_tokens: Target token count per chunk.
        overlap_tokens: Overlap tokens between chunks.
        duplicate_indices: Paragraph indices to skip as duplicates.

    Returns:
        List of chunk texts.
    """
    target_chars = target_tokens * CHARS_PER_TOKEN
    overlap_chars = overlap_tokens * CHARS_PER_TOKEN

    # Collect all paragraphs (filtering boilerplate)
    all_paragraphs: list[str] = []
    duplicate_indices = duplicate_indices or set()
    paragraph_index = 0
    for page_text in pages:
        # Split page into paragraphs (double newline or single newline)
        paragraphs = re.split(r"\n\s*\n|\n", page_text)
        for para in paragraphs:
            para_normalized = _normalize_text(para)
            if not para_normalized:
                continue
            if paragraph_index in duplicate_indices:
                paragraph_index += 1
                continue
            if _is_boilerplate(para_normalized):
                paragraph_index += 1
                continue
            all_paragraphs.append(para_normalized)
            paragraph_index += 1

    if not all_paragraphs:
        return []

    # Merge paragraphs into chunks
    chunks: list[str] = []
    current_chunk: list[str] = []
    current_chars = 0

    for para in all_paragraphs:
        para_chars = len(para)

        # Check if adding this paragraph would exceed target
        if current_chars + para_chars > target_chars and current_chunk:
            # Save current chunk
            chunk_text = " ".join(current_chunk)
            if chunk_text:
                chunks.append(chunk_text)

            # Start new chunk with overlap from previous
            if overlap_chars > 0 and chunk_text:
                overlap_text = chunk_text[-overlap_chars:] if len(chunk_text) > overlap_chars else chunk_text
                # Find last complete word in overlap
                last_space = overlap_text.rfind(" ")
                if last_space > 0:
                    overlap_text = overlap_text[last_space + 1 :]
                current_chunk = [overlap_text] if overlap_text else []
                current_chars = len(overlap_text)
            else:
                current_chunk = []
                current_chars = 0

        # Add paragraph to current chunk
        current_chunk.append(para)
        current_chars += para_chars + 1  # +1 for space

    # Add final chunk
    if current_chunk:
        chunk_text = " ".join(current_chunk)
        if chunk_text:
            chunks.append(chunk_text)

    return chunks


# ============================================================================
# Core Service Functions
# ============================================================================


async def chunk_single_pdf(
    db: AsyncSession,
    kap_report: KapReport,
    storage_base: Path,
) -> ChunkingResult:
    """Extract text from a PDF and create chunks.

    This function:
    - Reads PDF from local storage
    - Extracts text using pdfplumber
    - Filters boilerplate content
    - Splits into ~500 token chunks with ~50 token overlap
    - Creates DocumentChunk records
    - Updates KapReport.chunk_count and chunking_status

    Args:
        db: AsyncSession for database operations.
        kap_report: The KapReport to chunk PDF for.
        storage_base: Base directory for PDF storage.

    Returns:
        ChunkingResult with chunking outcome.
    """
    settings = get_settings()
    start_time = datetime.now(timezone.utc)

    # Parse disclosure index from local_pdf_path or pdf_url
    if kap_report.local_pdf_path:
        # Path format: {symbol}/{year}/{disclosure_index}.pdf
        disclosure_index = Path(kap_report.local_pdf_path).stem
    else:
        # Fallback: parse from pdf_url
        match = re.search(r"/(\d+)/?$", kap_report.pdf_url or "")
        disclosure_index = match.group(1) if match else None

    # Resolve symbol
    symbol = ""
    stock = getattr(kap_report, "stock", None)
    if stock and stock.symbol:
        symbol = stock.symbol
    elif kap_report.stock_id is not None:
        stock_result = await db.execute(
            select(Stock.symbol).where(Stock.id == kap_report.stock_id)
        )
        symbol = stock_result.scalar_one_or_none() or ""

    # Set status to CHUNKING
    kap_report.chunking_status = ChunkingStatus.CHUNKING.value
    await db.commit()

    try:
        # Build PDF path
        if kap_report.local_pdf_path:
            pdf_path = storage_base / kap_report.local_pdf_path
        else:
            # No local path - should not happen for completed downloads
            raise FileNotFoundError("No local PDF path available")

        # Extract text from PDF
        pages = _extract_text_from_pdf(pdf_path, max_retries=settings.pdf_transient_retry_count)

        # Check for empty extraction
        all_text = " ".join(pages)
        if not all_text.strip():
            # Empty PDF - mark as COMPLETED with error
            kap_report.chunking_status = ChunkingStatus.COMPLETED.value
            kap_report.chunk_count = 0
            kap_report.chunking_error = "empty_extraction"
            kap_report.chunked_at = datetime.now(timezone.utc)
            await db.commit()

            duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            return ChunkingResult(
                kap_report_id=kap_report.id,
                symbol=symbol,
                disclosure_index=disclosure_index,
                success=True,  # Technically successful, just empty
                chunks_created=0,
                status=ChunkingStatus.COMPLETED,
                error_message="empty_extraction",
                duration_ms=duration_ms,
            )

        # Find duplicate paragraphs within document
        duplicate_indices = _find_duplicate_paragraphs(pages)

        # Chunk paragraphs
        chunks = _chunk_paragraphs(
            pages,
            target_tokens=settings.chunk_target_tokens,
            overlap_tokens=settings.chunk_overlap_tokens,
            duplicate_indices=duplicate_indices,
        )

        # Check if all content was filtered
        if not chunks:
            kap_report.chunking_status = ChunkingStatus.COMPLETED.value
            kap_report.chunk_count = 0
            kap_report.chunking_error = "all_content_filtered"
            kap_report.chunked_at = datetime.now(timezone.utc)
            await db.commit()

            duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            return ChunkingResult(
                kap_report_id=kap_report.id,
                symbol=symbol,
                disclosure_index=disclosure_index,
                success=True,  # Technically successful, just filtered
                chunks_created=0,
                status=ChunkingStatus.COMPLETED,
                error_message="all_content_filtered",
                duration_ms=duration_ms,
            )

        # Insert chunks into database
        chunks_created = 0
        chunks_skipped = 0
        content_warning = _detect_content_validation_warning(
            title=kap_report.title,
            filing_type=kap_report.filing_type,
            chunks=chunks,
        )

        for chunk_index, chunk_text in enumerate(chunks):
            chunk_hash = _compute_chunk_hash(chunk_text)

            # Check for existing chunk (idempotency)
            existing = await db.execute(
                select(DocumentChunk.id)
                .where(DocumentChunk.kap_report_id == kap_report.id)
                .where(DocumentChunk.chunk_text_hash == chunk_hash)
                .limit(1)
            )
            if existing.scalar_one_or_none():
                chunks_skipped += 1
                continue

            # Create new chunk
            document_chunk = DocumentChunk(
                kap_report_id=kap_report.id,
                chunk_index=chunk_index,
                chunk_text=chunk_text,
                chunk_text_hash=chunk_hash,
                embedding_status="PENDING",
            )
            db.add(document_chunk)
            chunks_created += 1

        # Update KapReport
        kap_report.chunking_status = ChunkingStatus.COMPLETED.value
        kap_report.chunk_count = chunks_created
        kap_report.chunking_error = content_warning
        kap_report.chunked_at = datetime.now(timezone.utc)
        await db.commit()

        duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
        return ChunkingResult(
            kap_report_id=kap_report.id,
            symbol=symbol,
            disclosure_index=disclosure_index,
            success=True,
            chunks_created=chunks_created,
            chunks_skipped=chunks_skipped,
            status=ChunkingStatus.COMPLETED,
            duration_ms=duration_ms,
        )

    except FileNotFoundError as e:
        # PDF file not found - permanent failure
        kap_report.chunking_status = ChunkingStatus.FAILED.value
        kap_report.chunking_error = f"FileNotFoundError: {e}"
        await db.commit()

        duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
        return ChunkingResult(
            kap_report_id=kap_report.id,
            symbol=symbol,
            disclosure_index=disclosure_index,
            success=False,
            status=ChunkingStatus.FAILED,
            error_message=f"FileNotFoundError: {e}",
            duration_ms=duration_ms,
        )

    except Exception as e:
        # Other errors (PDFSyntaxError after retries, etc.)
        error_message = str(e)
        kap_report.chunking_status = ChunkingStatus.FAILED.value
        kap_report.chunking_error = error_message
        await db.commit()

        duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
        return ChunkingResult(
            kap_report_id=kap_report.id,
            symbol=symbol,
            disclosure_index=disclosure_index,
            success=False,
            status=ChunkingStatus.FAILED,
            error_message=error_message,
            duration_ms=duration_ms,
        )


async def batch_chunk_completed_pdfs(
    db: AsyncSession,
    limit: int = 50,
) -> ChunkingBatchResult:
    """Chunk all PDFs that have been downloaded but not yet chunked.

    Query KapReports where pdf_download_status='COMPLETED' AND chunking_status='PENDING'.
    Does NOT create PipelineLog - returns result only.

    Args:
        db: AsyncSession for database operations.
        limit: Maximum number of PDFs to chunk.

    Returns:
        ChunkingBatchResult with batch outcome.
    """
    settings = get_settings()
    storage_base = Path(settings.pdf_storage_path)

    # Query PDFs ready for chunking
    query = (
        select(KapReport)
        .where(
            KapReport.pdf_download_status == "COMPLETED",
            KapReport.chunking_status == ChunkingStatus.PENDING.value,
            KapReport.local_pdf_path.isnot(None),
        )
        .order_by(KapReport.published_at.desc())
        .limit(limit)
    )

    result = await db.execute(query)
    kap_reports = result.scalars().all()

    if not kap_reports:
        return ChunkingBatchResult(
            total_processed=0,
            successful=0,
            failed=0,
            status="success",
            results=[],
        )

    # Chunk each PDF
    results: list[ChunkingResult] = []
    successful = 0
    failed = 0

    for kap_report in kap_reports:
        chunking_result = await chunk_single_pdf(
            db=db,
            kap_report=kap_report,
            storage_base=storage_base,
        )
        results.append(chunking_result)

        if chunking_result.success:
            successful += 1
        else:
            failed += 1

    # Determine batch status
    if failed == 0:
        batch_status = "success"
    elif successful > 0:
        batch_status = "partial"
    else:
        batch_status = "failed"

    return ChunkingBatchResult(
        total_processed=len(kap_reports),
        successful=successful,
        failed=failed,
        status=batch_status,
        results=results,
    )
