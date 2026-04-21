"""Unit tests for RAG 2.0 canonical content memory."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.models.chunk_report_link import ChunkReportLink
from app.models.document_content import DocumentContent
from app.models.kap_report import KapReport
from app.models.stock import Stock
from app.services.agents.retrieval_agent import prepare_source_items
from app.services.data.mappers.kap_report_mapper import determine_rag_ingest_status
from app.services.pipeline.content_ingestion_service import persist_parsed_document
from app.services.pipeline.document_parser import ParsedDocument, ParsedElement, prepend_summary_element


class TestRagEligibility:
    def test_only_fr_and_far_are_rag_eligible(self):
        assert determine_rag_ingest_status("FR") == ("ELIGIBLE", None)
        assert determine_rag_ingest_status("FAR") == ("ELIGIBLE", None)
        assert determine_rag_ingest_status("ODA") == ("INELIGIBLE", "filing_type_filtered")


class TestParsedSummaryPrefix:
    def test_summary_is_inserted_as_first_atomic_element(self):
        parsed = ParsedDocument(
            parser_version="docling_markdown_v1",
            markdown="Body",
            elements=[
                ParsedElement(
                    element_type="paragraph",
                    text="Body",
                    markdown="Body",
                    page_start=1,
                    page_end=1,
                    token_estimate=1,
                )
            ],
        )

        enriched = prepend_summary_element(parsed, "Management summary")

        assert enriched.elements[0].element_type == "summary_prefix"
        assert enriched.elements[0].is_summary_prefix is True
        assert "Management summary" in enriched.markdown


class TestCanonicalContentPersistence:
    @pytest.mark.asyncio
    async def test_same_content_across_reports_creates_one_content_and_two_links(self, db_session):
        stock = Stock(symbol="THYAO", company_name="Turk Hava Yollari", is_active=True)
        db_session.add(stock)
        await db_session.commit()

        report_2023 = KapReport(
            stock_id=stock.id,
            title="2023 Faaliyet Raporu",
            filing_type="FAR",
            source_url="https://kap.test/2023",
            provider="pykap",
            pdf_download_status="COMPLETED",
            chunking_status="PENDING",
            rag_ingest_status="ELIGIBLE",
            published_at=datetime(2024, 3, 1, tzinfo=timezone.utc),
        )
        report_2024 = KapReport(
            stock_id=stock.id,
            title="2024 Faaliyet Raporu",
            filing_type="FAR",
            source_url="https://kap.test/2024",
            provider="pykap",
            pdf_download_status="COMPLETED",
            chunking_status="PENDING",
            rag_ingest_status="ELIGIBLE",
            published_at=datetime(2025, 3, 1, tzinfo=timezone.utc),
        )
        db_session.add_all([report_2023, report_2024])
        await db_session.commit()

        parsed = ParsedDocument(
            parser_version="docling_markdown_v1",
            markdown="Stable text",
            elements=[
                ParsedElement(
                    element_type="paragraph",
                    text="Stable text",
                    markdown="Stable text",
                    page_start=1,
                    page_end=1,
                    section_path="Strategy",
                    token_estimate=3,
                ),
            ],
        )

        first = await persist_parsed_document(db_session, report_2023, stock.id, parsed)
        await db_session.commit()
        second = await persist_parsed_document(db_session, report_2024, stock.id, parsed)
        await db_session.commit()

        contents = (await db_session.execute(select(DocumentContent))).scalars().all()
        links = (await db_session.execute(select(ChunkReportLink))).scalars().all()

        assert len(contents) == 1
        assert len(links) == 2
        assert first.created_count == 1
        assert second.created_count == 0

    def test_prepare_source_items_builds_consistency_evidence(self):
        chunks = [
            {
                "chunk_text": "Ayni bilgi",
                "metadata": {
                    "kap_report_id": 12,
                    "stock_symbol": "THYAO",
                    "report_title": "2024 Faaliyet Raporu",
                    "published_at": "2025-03-01T00:00:00+00:00",
                    "filing_type": "FAR",
                    "source_url": "https://kap.test/2024",
                    "report_links": [
                        {"kap_report_id": 12},
                        {"kap_report_id": 10},
                    ],
                    "published_years": [2023, 2024],
                    "consistency_count": 2,
                    "evidence_mode": "repeated_across_reports",
                    "latest_kap_report_id": 12,
                },
            }
        ]

        sources = prepare_source_items(chunks)

        assert len(sources) == 1
        assert sources[0].report_ids == [12, 10]
        assert sources[0].published_years == [2023, 2024]
        assert sources[0].evidence_mode == "repeated_across_reports"
        assert sources[0].evidence_note is not None
