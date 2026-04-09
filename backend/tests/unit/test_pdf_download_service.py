"""Unit tests for PDF download service.

Tests for:
- URL parsing (_parse_disclosure_index)
- Path building (_build_local_path)
- PDF validation (_validate_pdf_content)
- Error classification (_classify_error)
- Retry eligibility (_is_retry_eligible)
- Service functions (mocked httpx, mocked AsyncSession)
"""

import pytest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from app.services.data.pdf_download_service import (
    _parse_disclosure_index,
    _build_local_path,
    _validate_pdf_content,
    _classify_error,
    _is_retry_eligible,
    download_single_pdf,
    batch_download_pending_pdfs,
    batch_retry_failed_downloads,
    backfill_downloaded_pdfs_from_storage,
    PdfDownloadStatus,
    PdfDownloadResult,
    PdfBatchDownloadResult,
    MIN_PDF_SIZE,
    RETRY_ELIGIBLE_PATTERNS,
)


# ============================================================================
# URL Parsing Tests
# ============================================================================


class TestParseDisclosureIndex:
    """Tests for _parse_disclosure_index function."""

    def test_valid_url_with_index(self):
        """Test parsing valid KAP PDF URL."""
        url = "https://www.kap.org.tr/tr/api/BildirimPdf/12345678"
        result = _parse_disclosure_index(url)
        assert result == "12345678"

    def test_valid_url_with_trailing_slash(self):
        """Test parsing URL with trailing slash."""
        url = "https://www.kap.org.tr/tr/api/BildirimPdf/12345678/"
        result = _parse_disclosure_index(url)
        assert result == "12345678"

    def test_empty_url(self):
        """Test parsing empty URL."""
        result = _parse_disclosure_index("")
        assert result is None

    def test_none_url(self):
        """Test parsing None URL."""
        result = _parse_disclosure_index(None)
        assert result is None

    def test_malformed_url(self):
        """Test parsing malformed URL."""
        url = "not-a-valid-url"
        result = _parse_disclosure_index(url)
        assert result is None


# ============================================================================
# Path Building Tests
# ============================================================================


class TestBuildLocalPath:
    """Tests for _build_local_path function."""

    def test_basic_path(self):
        """Test basic path construction."""
        storage_base = Path("/data/pdfs")
        published_at = datetime(2024, 6, 15, tzinfo=timezone.utc)

        result = _build_local_path(
            symbol="THYAO",
            disclosure_index="12345678",
            published_at=published_at,
            storage_base=storage_base,
        )

        expected = Path("/data/pdfs/THYAO/2024/12345678.pdf")
        assert result == expected

    def test_lowercase_symbol_normalized(self):
        """Test that lowercase symbol is normalized to uppercase."""
        storage_base = Path("/data/pdfs")
        published_at = datetime(2024, 6, 15, tzinfo=timezone.utc)

        result = _build_local_path(
            symbol="thyao",
            disclosure_index="12345678",
            published_at=published_at,
            storage_base=storage_base,
        )

        assert "THYAO" in str(result)

    def test_null_published_at_uses_current_year(self):
        """Test that null published_at uses current year."""
        storage_base = Path("/data/pdfs")

        result = _build_local_path(
            symbol="THYAO",
            disclosure_index="12345678",
            published_at=None,
            storage_base=storage_base,
        )

        current_year = str(datetime.now().year)
        assert current_year in str(result)


# ============================================================================
# PDF Validation Tests
# ============================================================================


class TestValidatePdfContent:
    """Tests for _validate_pdf_content function."""

    def test_valid_pdf_content(self):
        """Test validation of valid PDF content."""
        # Create valid PDF content (magic bytes + minimum size)
        content = b"%PDF-1.4" + b"0" * (MIN_PDF_SIZE - 8)
        assert _validate_pdf_content(content) is True

    def test_invalid_magic_bytes(self):
        """Test rejection of content without PDF magic bytes."""
        content = b"HTML" + b"0" * (MIN_PDF_SIZE - 4)
        assert _validate_pdf_content(content) is False

    def test_content_too_small(self):
        """Test rejection of content smaller than minimum size."""
        content = b"%PDF-1.4" + b"0" * 100  # Less than MIN_PDF_SIZE
        assert _validate_pdf_content(content) is False

    def test_empty_content(self):
        """Test rejection of empty content."""
        assert _validate_pdf_content(b"") is False


# ============================================================================
# Error Classification Tests
# ============================================================================


class TestClassifyError:
    """Tests for _classify_error function."""

    def test_http_404_returns_not_available(self):
        """Test that 404 error returns NOT_AVAILABLE status."""
        response = MagicMock()
        response.status_code = 404
        error = httpx.HTTPStatusError("Not found", request=MagicMock(), response=response)

        status, message = _classify_error(error)
        assert status == PdfDownloadStatus.NOT_AVAILABLE
        assert "404" in message

    def test_http_500_returns_failed(self):
        """Test that 500 error returns FAILED status."""
        response = MagicMock()
        response.status_code = 500
        error = httpx.HTTPStatusError("Server error", request=MagicMock(), response=response)

        status, message = _classify_error(error)
        assert status == PdfDownloadStatus.FAILED
        assert "500" in message

    def test_timeout_returns_failed(self):
        """Test that timeout error returns FAILED status."""
        error = httpx.TimeoutException("Request timed out")

        status, message = _classify_error(error)
        assert status == PdfDownloadStatus.FAILED
        assert "Timeout" in message

    def test_connect_error_returns_failed(self):
        """Test that connect error returns FAILED status."""
        error = httpx.ConnectError("Connection refused")

        status, message = _classify_error(error)
        assert status == PdfDownloadStatus.FAILED
        assert "ConnectError" in message

    def test_oserror_returns_failed(self):
        """Test that OS error returns FAILED status."""
        error = OSError("Permission denied")

        status, message = _classify_error(error)
        assert status == PdfDownloadStatus.FAILED
        assert "OSError" in message

    def test_value_error_returns_not_available(self):
        """Test that ValueError returns NOT_AVAILABLE status."""
        error = ValueError("Invalid URL format")

        status, message = _classify_error(error)
        assert status == PdfDownloadStatus.NOT_AVAILABLE
        assert "Invalid URL" in message


# ============================================================================
# Retry Eligibility Tests
# ============================================================================


class TestIsRetryEligible:
    """Tests for _is_retry_eligible function."""

    def test_timeout_is_retry_eligible(self):
        """Test that timeout error is retry eligible."""
        assert _is_retry_eligible("Timeout: Request timed out") is True

    def test_connect_error_is_retry_eligible(self):
        """Test that connect error is retry eligible."""
        assert _is_retry_eligible("ConnectError: Connection refused") is True

    def test_http_500_is_retry_eligible(self):
        """Test that HTTP 500 error is retry eligible."""
        assert _is_retry_eligible("HTTP 500: Internal server error") is True

    def test_http_502_is_retry_eligible(self):
        """Test that HTTP 502 error is retry eligible."""
        assert _is_retry_eligible("HTTP 502: Bad gateway") is True

    def test_invalid_pdf_is_retry_eligible(self):
        """Test that invalid PDF error is retry eligible."""
        assert _is_retry_eligible("Invalid PDF: Content validation failed") is True

    def test_oserror_not_retry_eligible(self):
        """Test that OS error is NOT retry eligible."""
        assert _is_retry_eligible("OSError: Permission denied") is False

    def test_http_404_not_retry_eligible(self):
        """Test that 404 error is NOT retry eligible (should be NOT_AVAILABLE anyway)."""
        assert _is_retry_eligible("HTTP 404: Not found") is False

    def test_disk_error_not_retry_eligible(self):
        """Test that disk error is NOT retry eligible."""
        assert _is_retry_eligible("disk full") is False

    def test_empty_message_not_retry_eligible(self):
        """Test that empty message is NOT retry eligible."""
        assert _is_retry_eligible("") is False


# ============================================================================
# Service Function Tests (Mocked)
# ============================================================================


class TestDownloadSinglePdf:
    """Tests for download_single_pdf function with mocked dependencies."""

    @pytest.mark.asyncio
    async def test_invalid_url_returns_not_available(self):
        """Test that invalid URL returns NOT_AVAILABLE status."""
        db = AsyncMock()
        kap_report = MagicMock()
        kap_report.id = 1
        kap_report.pdf_url = None
        kap_report.stock = MagicMock()
        kap_report.stock.symbol = "THYAO"

        result = await download_single_pdf(
            db=db,
            kap_report=kap_report,
            storage_base=Path("/data/pdfs"),
        )

        assert result.status == PdfDownloadStatus.NOT_AVAILABLE
        assert result.success is False

    @pytest.mark.asyncio
    async def test_successful_download(self):
        """Test successful PDF download."""
        db = AsyncMock()
        kap_report = MagicMock()
        kap_report.id = 1
        kap_report.pdf_url = "https://www.kap.org.tr/tr/api/BildirimPdf/12345678"
        kap_report.published_at = datetime(2024, 6, 15, tzinfo=timezone.utc)
        kap_report.stock = MagicMock()
        kap_report.stock.symbol = "THYAO"

        # Mock httpx client
        valid_pdf = b"%PDF-1.4" + b"0" * (MIN_PDF_SIZE - 8)

        with patch("app.services.data.pdf_download_service.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.content = valid_pdf
            mock_response.raise_for_status = MagicMock()

            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

            # Mock Path.write_bytes
            with patch.object(Path, "write_bytes"):
                result = await download_single_pdf(
                    db=db,
                    kap_report=kap_report,
                    storage_base=Path("/data/pdfs"),
                )

        assert result.status == PdfDownloadStatus.COMPLETED
        assert result.success is True
        assert result.file_size == len(valid_pdf)


class TestBatchDownloadPendingPdfs:
    """Tests for batch_download_pending_pdfs function."""

    @pytest.mark.asyncio
    async def test_no_pending_pdfs(self):
        """Test handling of no pending PDFs."""
        db = AsyncMock()

        # Mock query returning empty result
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(return_value=mock_result)

        result = await batch_download_pending_pdfs(db=db, limit=50)

        assert result.total_processed == 0
        assert result.successful == 0
        assert result.status == "success"


class TestBatchRetryFailedDownloads:
    """Tests for batch_retry_failed_downloads function."""

    @pytest.mark.asyncio
    async def test_no_failed_pdfs(self):
        """Test handling of no failed PDFs."""
        db = AsyncMock()

        # Mock query returning empty result
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(return_value=mock_result)

        result = await batch_retry_failed_downloads(db=db, limit=50)

        assert result.total_processed == 0
        assert result.status == "success"


class TestBackfillDownloadedPdfs:
    """Tests for syncing on-disk PDFs back into KapReport state."""

    @pytest.mark.asyncio
    async def test_backfill_updates_matching_report(self, db_session):
        from app.models.kap_report import KapReport
        from app.models.stock import Stock

        stock = Stock(
            symbol="THYAO",
            company_name="Turkish Airlines",
            sector="Airlines",
            exchange="BIST",
            is_active=True,
        )
        db_session.add(stock)
        await db_session.flush()

        report = KapReport(
            stock_id=stock.id,
            title="THYAO Finansal Rapor 2024",
            filing_type="FR",
            pdf_url="https://www.kap.org.tr/tr/api/BildirimPdf/1076581",
            source_url="https://www.kap.org.tr/tr/Bildirim/1076581",
            sync_status="COMPLETED",
            pdf_download_status=PdfDownloadStatus.PENDING.value,
        )
        db_session.add(report)
        await db_session.commit()

        storage_base = Path("C:/tmp/test-pdfs")
        file_path = storage_base / "THYAO" / "2024" / "1076581.pdf"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(b"%PDF-1.4" + b"0" * 2048)

        try:
            result = await backfill_downloaded_pdfs_from_storage(db_session, storage_base=storage_base)
            await db_session.refresh(report)

            assert result.matched == 1
            assert result.updated == 1
            assert report.local_pdf_path == "THYAO/2024/1076581.pdf"
            assert report.pdf_download_status == PdfDownloadStatus.COMPLETED.value
            assert report.pdf_file_size == file_path.stat().st_size
            assert report.pdf_download_error is None
        finally:
            if file_path.exists():
                file_path.unlink()
            if file_path.parent.exists():
                file_path.parent.rmdir()
            if file_path.parent.parent.exists():
                file_path.parent.parent.rmdir()
            if storage_base.exists():
                storage_base.rmdir()
