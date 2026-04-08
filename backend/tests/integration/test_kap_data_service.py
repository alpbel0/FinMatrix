"""Integration tests for kap_data_service.

Tests with real database session but mocked provider.
"""

import pytest
from datetime import date, timedelta
from unittest.mock import patch, MagicMock

from sqlalchemy import select

from app.models.stock import Stock
from app.models.kap_report import KapReport
from app.models.pipeline_log import PipelineLog
from app.services.data.kap_data_service import (
    sync_kap_filings,
    batch_sync_kap_filings,
)
from app.services.data.provider_models import KapFiling, DataSource
from tests.factories import create_kap_filing, create_kap_filings_batch


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_provider():
    """Create a mock provider for testing."""
    provider = MagicMock()
    provider.get_kap_filings = MagicMock()
    return provider


# ============================================================================
# sync_kap_filings Integration Tests
# ============================================================================


class TestSyncKapFilingsIntegration:
    """Integration tests for sync_kap_filings with real database."""

    @pytest.mark.asyncio
    async def test_sync_persists_to_database(self, db_session, mock_provider):
        """Synced KAP filings should persist to kap_reports table."""
        # Create stock
        stock = Stock(symbol="THYAO", company_name="Turk Hava Yollari", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        # Create filings
        filings = create_kap_filings_batch(symbol="THYAO", num_filings=10)
        mock_provider.get_kap_filings.return_value = filings

        with patch(
            "app.services.data.kap_data_service.get_provider_for_kap_filings",
            return_value=mock_provider
        ):
            result = await sync_kap_filings(db_session, "THYAO", filing_types=["FR"], days_back=30)

        assert result.success is True
        assert result.filings_processed == 10

        # Verify data persisted
        db_result = await db_session.execute(
            select(KapReport).where(KapReport.stock_id == stock.id)
        )
        db_reports = list(db_result.scalars().all())

        assert len(db_reports) == 10
        # Verify fields persisted correctly
        for db_report in db_reports:
            assert db_report.title is not None
            assert db_report.filing_type is not None
            assert db_report.source_url is not None

    @pytest.mark.asyncio
    async def test_sync_upsert_updates_existing_filings(self, db_session, mock_provider):
        """Upsert should update existing filing records."""
        # Create stock
        stock = Stock(symbol="THYAO", company_name="Test", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        # First sync with original title
        filing_v1 = create_kap_filing(
            title="Financial Report Q1",
            disclosure_index=12345678,
        )
        mock_provider.get_kap_filings.return_value = [filing_v1]

        with patch(
            "app.services.data.kap_data_service.get_provider_for_kap_filings",
            return_value=mock_provider
        ):
            await sync_kap_filings(db_session, "THYAO", filing_types=["FR"])

        # Second sync with updated title (same disclosure_index -> same source_url)
        filing_v2 = create_kap_filing(
            title="Financial Report Q1 2024 (Updated)",
            disclosure_index=12345678,  # Same disclosure index -> same source_url
        )
        mock_provider.get_kap_filings.return_value = [filing_v2]

        with patch(
            "app.services.data.kap_data_service.get_provider_for_kap_filings",
            return_value=mock_provider
        ):
            await sync_kap_filings(db_session, "THYAO", filing_types=["FR"])

        # Verify only one record exists with updated title
        db_result = await db_session.execute(
            select(KapReport).where(KapReport.stock_id == stock.id)
        )
        db_reports = list(db_result.scalars().all())

        assert len(db_reports) == 1
        assert db_reports[0].title == "Financial Report Q1 2024 (Updated)"

    @pytest.mark.asyncio
    async def test_sync_multiple_stocks(self, db_session, mock_provider):
        """Should handle syncing multiple stocks independently."""
        # Create stocks
        for symbol in ["THYAO", "GARAN", "ASELS"]:
            stock = Stock(symbol=symbol, company_name=f"{symbol} Company", is_active=True)
            db_session.add(stock)
        await db_session.commit()

        filings = create_kap_filings_batch(symbol="TEST", num_filings=5)
        mock_provider.get_kap_filings.return_value = filings

        with patch(
            "app.services.data.kap_data_service.get_provider_for_kap_filings",
            return_value=mock_provider
        ):
            for symbol in ["THYAO", "GARAN", "ASELS"]:
                result = await sync_kap_filings(db_session, symbol, filing_types=["FR"])
                assert result.success is True

        # Verify each stock has its own filings
        for symbol in ["THYAO", "GARAN", "ASELS"]:
            stock_result = await db_session.execute(
                select(Stock).where(Stock.symbol == symbol)
            )
            stock = stock_result.scalar_one()
            report_result = await db_session.execute(
                select(KapReport).where(KapReport.stock_id == stock.id)
            )
            reports = list(report_result.scalars().all())
            assert len(reports) == 5

    @pytest.mark.asyncio
    async def test_sync_thyao_last_10_filings(self, db_session, mock_provider):
        """ROADMAP requirement: THYAO için son 10 filing DB'ye yaz."""
        # Create stock
        stock = Stock(symbol="THYAO", company_name="Turk Hava Yollari", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        # Create 10 filings
        filings = create_kap_filings_batch(symbol="THYAO", num_filings=10)
        mock_provider.get_kap_filings.return_value = filings

        with patch(
            "app.services.data.kap_data_service.get_provider_for_kap_filings",
            return_value=mock_provider
        ):
            result = await sync_kap_filings(db_session, "THYAO", filing_types=["FR"], days_back=30)

        assert result.success is True
        assert result.filings_processed == 10

        # Verify DB state
        db_result = await db_session.execute(
            select(KapReport)
            .where(KapReport.stock_id == stock.id)
            .order_by(KapReport.published_at.desc())
            .limit(10)
        )
        db_reports = list(db_result.scalars().all())

        assert len(db_reports) == 10

    @pytest.mark.asyncio
    async def test_sync_enrichment_fields_persisted(self, db_session, mock_provider):
        """Enrichment fields (summary, attachment_count, is_late, related_stocks) should persist."""
        # Create stock
        stock = Stock(symbol="THYAO", company_name="Test", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        # Create filing with enrichment data
        filing = KapFiling(
            symbol="THYAO",
            title="Financial Report with Enrichment",
            filing_type="FR",
            source_url="https://www.kap.org.tr/tr/Bildirim/999999",
            pdf_url="https://www.kap.org.tr/tr/api/BildirimPdf/999999",
            provider=DataSource.KAPSDK,
            summary="Quarterly financial results show 15% increase in revenue",
            attachment_count=3,
            is_late=True,
            related_stocks="GARAN,ASELS",
        )
        mock_provider.get_kap_filings.return_value = [filing]

        with patch(
            "app.services.data.kap_data_service.get_provider_for_kap_filings",
            return_value=mock_provider
        ):
            result = await sync_kap_filings(db_session, "THYAO", filing_types=["FR"])

        assert result.success is True

        # Verify enrichment fields persisted
        db_result = await db_session.execute(
            select(KapReport).where(KapReport.stock_id == stock.id)
        )
        db_report = db_result.scalar_one_or_none()

        assert db_report is not None
        assert db_report.summary == "Quarterly financial results show 15% increase in revenue"
        assert db_report.attachment_count == 3
        assert db_report.is_late is True
        assert db_report.related_stocks == ["GARAN", "ASELS"]  # JSONB array

    @pytest.mark.asyncio
    async def test_duplicate_detection_same_source_url(self, db_session, mock_provider):
        """Duplicate filings (same source_url) should be updated, not duplicated."""
        # Create stock
        stock = Stock(symbol="THYAO", company_name="Test", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        # Same disclosure index means same source_url
        filing1 = create_kap_filing(title="Filing V1", disclosure_index=12345678)
        filing2 = create_kap_filing(title="Filing V2", disclosure_index=12345678)
        filing3 = create_kap_filing(title="Different Filing", disclosure_index=87654321)

        # First sync with filing1
        mock_provider.get_kap_filings.return_value = [filing1]
        with patch(
            "app.services.data.kap_data_service.get_provider_for_kap_filings",
            return_value=mock_provider
        ):
            result1 = await sync_kap_filings(db_session, "THYAO", filing_types=["FR"])

        assert result1.filings_processed == 1

        # Second sync with filing2 and filing3
        mock_provider.get_kap_filings.return_value = [filing2, filing3]
        with patch(
            "app.services.data.kap_data_service.get_provider_for_kap_filings",
            return_value=mock_provider
        ):
            result2 = await sync_kap_filings(db_session, "THYAO", filing_types=["FR"])

        # Should have 2 filings total (one updated, one new)
        assert result2.filings_processed == 2

        # Verify DB has exactly 2 records
        db_result = await db_session.execute(
            select(KapReport).where(KapReport.stock_id == stock.id)
        )
        db_reports = list(db_result.scalars().all())

        assert len(db_reports) == 2

        # Verify title was updated for the duplicate
        titles = [r.title for r in db_reports]
        assert "Filing V2" in titles
        assert "Different Filing" in titles


# ============================================================================
# batch_sync_kap_filings Integration Tests
# ============================================================================


class TestBatchSyncKapFilingsIntegration:
    """Integration tests for batch_sync_kap_filings with real database."""

    @pytest.mark.asyncio
    async def test_batch_sync_pipeline_log_persists(self, db_session, mock_provider):
        """PipelineLog should be persisted with correct details."""
        # Create stocks
        for symbol in ["THYAO", "GARAN"]:
            stock = Stock(symbol=symbol, company_name=f"{symbol} Company", is_active=True)
            db_session.add(stock)
        await db_session.commit()

        filings = create_kap_filings_batch(symbol="TEST", num_filings=5)
        mock_provider.get_kap_filings.return_value = filings

        with patch(
            "app.services.data.kap_data_service.get_provider_for_kap_filings",
            return_value=mock_provider
        ):
            result = await batch_sync_kap_filings(
                db_session, ["THYAO", "GARAN"], filing_types=["FR"], days_back=30
            )

        # Verify PipelineLog persisted
        log_result = await db_session.execute(
            select(PipelineLog).where(PipelineLog.run_id == result.run_id)
        )
        saved_log = log_result.scalar_one()

        assert saved_log.pipeline_name == "kap_filings_sync"
        assert saved_log.status == "success"
        assert saved_log.processed_count == 10  # 5 filings * 2 symbols
        assert saved_log.details["filing_types"] == ["FR"]
        assert saved_log.details["days_back"] == 30
        assert "THYAO" in saved_log.details["successful_symbols"]
        assert "GARAN" in saved_log.details["successful_symbols"]

    @pytest.mark.asyncio
    async def test_batch_sync_partial_logs_failures(self, db_session, mock_provider):
        """Partial failure should log failed symbols."""
        # Create stocks
        for symbol in ["THYAO", "GARAN", "INVALID"]:
            stock = Stock(symbol=symbol, company_name=f"{symbol} Company", is_active=True)
            db_session.add(stock)
        await db_session.commit()

        filings = create_kap_filings_batch(symbol="TEST", num_filings=5)

        def mock_get_filings(symbol, **kwargs):
            if symbol == "INVALID":
                raise Exception("Provider error")
            return filings

        mock_provider.get_kap_filings.side_effect = mock_get_filings

        with patch(
            "app.services.data.kap_data_service.get_provider_for_kap_filings",
            return_value=mock_provider
        ):
            result = await batch_sync_kap_filings(
                db_session, ["THYAO", "GARAN", "INVALID"], filing_types=["FR"]
            )

        assert result.status == "partial"

        # Verify log contains failure info
        log_result = await db_session.execute(
            select(PipelineLog).where(PipelineLog.run_id == result.run_id)
        )
        saved_log = log_result.scalar_one()

        assert "INVALID" in saved_log.details["failed_symbols"]
        assert saved_log.error_message is not None


# ============================================================================
# End-to-End KAP Sync Flow Tests
# ============================================================================


class TestKapSyncEndToEnd:
    """End-to-end tests for KAP sync flow."""

    @pytest.mark.asyncio
    async def test_full_sync_flow(self, db_session, mock_provider):
        """Test complete sync flow from stock creation to database persistence."""
        # Step 1: Create stock
        stock = Stock(symbol="THYAO", company_name="Turk Hava Yollari", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        # Step 2: Prepare mock data
        filings = create_kap_filings_batch(
            symbol="THYAO",
            num_filings=10,
            filing_types=["FR", "FAR"],
        )
        mock_provider.get_kap_filings.return_value = filings

        # Step 3: Run sync
        with patch(
            "app.services.data.kap_data_service.get_provider_for_kap_filings",
            return_value=mock_provider
        ):
            result = await sync_kap_filings(
                db_session, "THYAO", filing_types=["FR", "FAR"], days_back=90
            )

        # Step 4: Verify results
        assert result.success is True
        assert result.filings_processed == 10

        # Step 5: Verify database state
        db_result = await db_session.execute(
            select(KapReport)
            .where(KapReport.stock_id == stock.id)
            .order_by(KapReport.published_at.desc())
        )
        db_reports = list(db_result.scalars().all())

        assert len(db_reports) == 10
        # Verify all filings have required fields
        for report in db_reports:
            assert report.title is not None
            assert report.filing_type in ["FR", "FAR"]
            assert report.source_url is not None
            assert report.provider in ["pykap", "kap_sdk"]
            assert report.sync_status == "PENDING"
            assert report.chunk_count == 0