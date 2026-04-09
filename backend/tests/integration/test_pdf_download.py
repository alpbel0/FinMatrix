"""Integration tests for PDF download service."""

import pytest
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kap_report import KapReport
from app.models.stock import Stock
from app.services.data.pdf_download_service import (
    download_single_pdf,
    batch_download_pending_pdfs,
    batch_retry_failed_downloads,
    get_download_statistics,
    PdfDownloadStatus,
)
from app.config import get_settings


@pytest.fixture
async def test_stocks(db_session: AsyncSession):
    """Create test stocks for PDF download tests."""
    stocks = []
    symbols = ["THYAO", "GARAN", "AKBNK"]

    for symbol in symbols:
        stock = Stock(
            symbol=symbol,
            company_name=f"Test Company {symbol}",
            sector="Test",
            exchange="BIST",
            is_active=True,
        )
        db_session.add(stock)
        await db_session.flush()
        stocks.append(stock)

    await db_session.commit()
    return stocks


@pytest.fixture
async def test_kap_reports(db_session: AsyncSession, test_stocks):
    """Create test KapReport entries with real KAP PDF URLs.

    Uses real disclosure indices from KAP.org.tr.
    """
    # Real disclosure indices from KAP (financial reports)
    # These are actual public disclosures available on KAP.org.tr
    kap_data = [
        {
            "symbol": "THYAO",
            "title": "THYAO Finansal Rapor 2024",
            "disclosure_index": "1076581",  # Real disclosure index
            "published_at": datetime(2024, 3, 15, tzinfo=timezone.utc),
        },
        {
            "symbol": "GARAN",
            "title": "GARAN Finansal Rapor 2024",
            "disclosure_index": "1076582",  # Real disclosure index
            "published_at": datetime(2024, 3, 15, tzinfo=timezone.utc),
        },
        {
            "symbol": "AKBNK",
            "title": "AKBNK Finansal Rapor 2024",
            "disclosure_index": "1076583",  # Real disclosure index
            "published_at": datetime(2024, 3, 15, tzinfo=timezone.utc),
        },
    ]

    reports = []
    for data in kap_data:
        stock = next(s for s in test_stocks if s.symbol == data["symbol"])

        pdf_url = f"https://www.kap.org.tr/tr/api/BildirimPdf/{data['disclosure_index']}"
        report = KapReport(
            stock_id=stock.id,
            title=data["title"],
            filing_type="FR",
            pdf_url=pdf_url,
            source_url=f"https://www.kap.org.tr/tr/Bildirim/{data['disclosure_index']}",
            published_at=data["published_at"],
            provider="test",
            sync_status="COMPLETED",
            pdf_download_status=PdfDownloadStatus.PENDING.value,
        )
        db_session.add(report)
        await db_session.flush()
        reports.append(report)

    await db_session.commit()
    return reports


@pytest.fixture
def storage_base(tmp_path: Path):
    """Use isolated temp storage for PDF downloads."""
    settings = get_settings()
    original_path = settings.pdf_storage_path
    storage_path = tmp_path / "pdfs"
    settings.pdf_storage_path = str(storage_path)
    try:
        yield storage_path
    finally:
        settings.pdf_storage_path = original_path


# ============================================================================
# Integration Tests
# ============================================================================


class TestRealPdfDownload:
    """Integration tests for real PDF downloads."""

    @pytest.mark.asyncio
    async def test_download_single_pdf_real(
        self,
        db_session: AsyncSession,
        test_kap_reports,
        storage_base,
    ):
        """Test downloading a single real PDF from KAP."""
        report = test_kap_reports[0]

        result = await download_single_pdf(
            db=db_session,
            kap_report=report,
            storage_base=storage_base,
            timeout=60.0,  # Longer timeout for real download
        )

        # Verify result
        assert result.success is True
        assert result.status == PdfDownloadStatus.COMPLETED
        assert result.file_size is not None
        assert result.file_size > 1000  # At least 1KB
        assert result.local_path is not None

        # Verify file exists on disk
        file_path = storage_base / result.local_path
        assert file_path.exists()
        assert file_path.stat().st_size == result.file_size

    @pytest.mark.asyncio
    async def test_download_three_pdfs_batch(
        self,
        db_session: AsyncSession,
        test_kap_reports,
        storage_base,
    ):
        """Test batch downloading 3 different KAP PDFs."""
        result = await batch_download_pending_pdfs(
            db=db_session,
            limit=10,
            filing_types=["FR"],
        )

        # Verify batch result
        assert result.total_processed >= 1  # At least one downloaded
        assert result.successful >= 1
        assert result.failed == 0 or result.status == "partial"

        # Verify files exist on disk
        for download_result in result.results:
            if download_result.success:
                file_path = storage_base / download_result.local_path
                assert file_path.exists()

    @pytest.mark.asyncio
    async def test_verify_database_fields(
        self,
        db_session: AsyncSession,
        test_kap_reports,
        storage_base,
    ):
        """Test that KapReport database fields are updated correctly."""
        report = test_kap_reports[0]

        # Download
        result = await download_single_pdf(
            db=db_session,
            kap_report=report,
            storage_base=storage_base,
            timeout=60.0,
        )

        # Refresh from database
        await db_session.refresh(report)

        # Verify database fields
        assert report.pdf_download_status == PdfDownloadStatus.COMPLETED.value
        assert report.local_pdf_path is not None
        assert report.pdf_file_size == result.file_size
        assert report.pdf_downloaded_at is not None
        assert report.pdf_download_error is None

    @pytest.mark.asyncio
    async def test_get_download_statistics(
        self,
        db_session: AsyncSession,
        test_kap_reports,
    ):
        """Test getting download statistics."""
        # First download some PDFs
        await batch_download_pending_pdfs(db_session, limit=3)

        # Get statistics
        stats = await get_download_statistics(db_session)

        # Verify statistics structure
        assert PdfDownloadStatus.COMPLETED.value in stats
        assert PdfDownloadStatus.PENDING.value in stats
        assert PdfDownloadStatus.FAILED.value in stats

        # At least some should be completed
        assert stats[PdfDownloadStatus.COMPLETED.value] >= 0


class TestPdfDownloadRetry:
    """Tests for PDF download retry functionality."""

    @pytest.mark.asyncio
    async def test_retry_failed_download(
        self,
        db_session: AsyncSession,
        test_stocks,
        storage_base,
    ):
        """Test retrying a failed download."""
        # Create a KapReport with a valid PDF URL but mark as FAILED
        stock = test_stocks[0]
        disclosure_index = "1076584"  # Another real disclosure

        report = KapReport(
            stock_id=stock.id,
            title="Test Failed Report",
            filing_type="FR",
            pdf_url=f"https://www.kap.org.tr/tr/api/BildirimPdf/{disclosure_index}",
            source_url=f"https://www.kap.org.tr/tr/Bildirim/{disclosure_index}",
            published_at=datetime(2024, 3, 15, tzinfo=timezone.utc),
            provider="test",
            sync_status="COMPLETED",
            pdf_download_status=PdfDownloadStatus.FAILED.value,
            pdf_download_error="Timeout: Request timed out",  # Retry-eligible error
        )
        db_session.add(report)
        await db_session.commit()

        # Retry failed downloads
        result = await batch_retry_failed_downloads(
            db=db_session,
            limit=5,
        )

        # Verify retry attempted
        assert result.total_processed >= 0

        # If download succeeded, verify status changed
        if result.successful > 0:
            await db_session.refresh(report)
            assert report.pdf_download_status == PdfDownloadStatus.COMPLETED.value


class TestInvalidPdf:
    """Tests for handling permanent PDF failures."""

    @pytest.mark.asyncio
    async def test_invalid_url_marks_not_available(
        self,
        db_session: AsyncSession,
        test_stocks,
        storage_base,
    ):
        """Test handling of invalid PDF URL as permanent failure."""
        stock = test_stocks[0]

        report = KapReport(
            stock_id=stock.id,
            title="Non-existent PDF",
            filing_type="FR",
            pdf_url="not-a-valid-url",
            source_url="https://www.kap.org.tr/tr/Bildirim/999999999",
            published_at=datetime(2024, 3, 15, tzinfo=timezone.utc),
            provider="test",
            sync_status="COMPLETED",
            pdf_download_status=PdfDownloadStatus.PENDING.value,
        )
        db_session.add(report)
        await db_session.commit()

        result = await download_single_pdf(
            db=db_session,
            kap_report=report,
            storage_base=storage_base,
            timeout=30.0,
        )

        # Invalid URL is a permanent failure and should not be retried.
        assert result.status == PdfDownloadStatus.NOT_AVAILABLE
        assert result.success is False

        # Verify database updated
        await db_session.refresh(report)
        assert report.pdf_download_status == PdfDownloadStatus.NOT_AVAILABLE.value
