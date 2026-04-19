"""Tests for agent trace/log output in orchestrated pipeline.

These tests verify that ChatPipelineResult and trace logging functions
correctly capture and structure debug information from the agent pipeline.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.chat import (
    FinancialMetricSnapshot,
    NumericalAnalysisResult,
    QueryClassificationResult,
    QueryUnderstandingResult,
    RAGResponse,
    RetrievalAgentResult,
    SourceItem,
    TextAnalysisResult,
)
from app.schemas.enums import DocumentType, QueryIntent, QueryType
from app.services.agents.merger import merge_analysis_results
from app.services.chat_trace_service import (
    ChatPipelineResult,
    _build_response_payload,
    _build_retrieval_payload,
    _summarize_sources,
    _truncate_text,
)
from app.services.agents.merger import _dedupe_sources
from app.services.data.provider_models import PeriodType


class TestTextTruncation:
    """Tests for text truncation utility."""

    def test_truncate_text_shorter_than_max(self):
        text = "short text"
        result = _truncate_text(text, max_length=500)
        assert result == text

    def test_truncate_text_longer_than_max(self):
        text = "a" * 1000
        result = _truncate_text(text, max_length=100)
        assert len(result) == 100
        assert result == "a" * 100

    def test_truncate_text_default_max_length(self):
        text = "x" * 600
        result = _truncate_text(text)
        assert len(result) == 500


class TestSourceSummarization:
    """Tests for source summarization in traces."""

    def test_summarize_sources_truncates_preview(self):
        source = SourceItem(
            kap_report_id=1,
            stock_symbol="THYAO",
            report_title="THYAO Faaliyet Raporu 2025",
            published_at=None,
            filing_type="FAR",
            source_url="https://kap.org/1",
            chunk_preview="a" * 300,  # Long preview > 160 chars
        )
        summarized = _summarize_sources([source])

        assert len(summarized) == 1
        assert len(summarized[0]["chunk_preview"]) <= 160

    def test_summarize_sources_limits_to_three(self):
        sources = [
            SourceItem(
                kap_report_id=i,
                stock_symbol="THYAO",
                report_title=f"Report {i}",
                published_at=None,
                filing_type="FR",
                source_url=f"https://kap.org/{i}",
                chunk_preview="Preview",
            )
            for i in range(5)
        ]
        summarized = _summarize_sources(sources)

        assert len(summarized) == 3

    def test_summarize_sources_handles_dict_without_model_dump(self):
        source = {
            "kap_report_id": 1,
            "stock_symbol": "THYAO",
            "report_title": "Report",
            "published_at": None,
            "filing_type": "FR",
            "source_url": "https://kap.org/1",
            "chunk_preview": "Preview",
        }
        summarized = _summarize_sources([source])

        assert len(summarized) == 1
        assert summarized[0]["stock_symbol"] == "THYAO"


class TestRetrievalPayload:
    """Tests for retrieval payload building."""

    def test_build_retrieval_payload_basic(self):
        retrieval = RetrievalAgentResult(
            chunks=[
                {"chunk_text": "Test chunk 1", "score": 0.5, "metadata": {"stock_symbol": "THYAO"}},
                {"chunk_text": "Test chunk 2", "score": 0.8, "metadata": {"stock_symbol": "THYAO"}},
            ],
            sources=[],
            has_sufficient_context=True,
            retrieval_confidence=0.75,
            context_total_chars=1500,
        )
        payload = _build_retrieval_payload(retrieval)

        assert payload["chunk_count"] == 2
        assert payload["retrieval_confidence"] == 0.75
        assert payload["context_total_chars"] == 1500
        assert payload["has_sufficient_context"] is True
        assert len(payload["chunks_preview"]) == 2

    def test_build_retrieval_payload_truncates_chunk_preview(self):
        retrieval = RetrievalAgentResult(
            chunks=[
                {
                    "chunk_text": "x" * 300,
                    "score": 0.5,
                    "metadata": {"stock_symbol": "THYAO", "kap_report_id": 1, "filing_type": "FR", "source_url": "https://kap.org/1"},
                },
            ],
            sources=[],
            has_sufficient_context=False,
            retrieval_confidence=0.3,
            context_total_chars=300,
        )
        payload = _build_retrieval_payload(retrieval)

        assert len(payload["chunks_preview"][0]["chunk_preview"]) <= 200


class TestResponsePayload:
    """Tests for response payload building."""

    def test_build_response_payload_truncates_answer(self):
        response = RAGResponse(
            answer_text="a" * 500,
            sources=[],
            stock_symbol="THYAO",
            document_type=DocumentType.FR,
            insufficient_context=False,
        )
        payload = _build_response_payload(response)

        assert len(payload["answer_preview"]) <= 300
        assert payload["source_count"] == 0
        assert payload["stock_symbol"] == "THYAO"

    def test_build_response_payload_document_type_value(self):
        response = RAGResponse(
            answer_text="Test answer",
            sources=[],
            stock_symbol=None,
            document_type=DocumentType.FAR,
            insufficient_context=True,
        )
        payload = _build_response_payload(response)

        assert payload["document_type"] == "FAR"
        assert payload["insufficient_context"] is True


class TestChatPipelineResult:
    """Tests for ChatPipelineResult structure."""

    def test_pipeline_result_has_required_fields(self):
        response = RAGResponse(
            answer_text="Test answer",
            sources=[],
            stock_symbol="THYAO",
            document_type=DocumentType.FR,
            insufficient_context=False,
        )
        understanding = QueryUnderstandingResult(
            normalized_query="THYAO analiz",
            candidate_symbol="THYAO",
            document_type=DocumentType.FR,
            intent=QueryIntent.SUMMARY,
            confidence=0.9,
            suggested_rewrite=None,
        )
        retrieval = RetrievalAgentResult(
            chunks=[],
            sources=[],
            has_sufficient_context=True,
            retrieval_confidence=0.8,
            context_total_chars=1000,
        )

        result = ChatPipelineResult(
            response=response,
            understanding=understanding,
            resolved_symbol="THYAO",
            retrieval=retrieval,
            memory_context="",
        )

        assert result.response.answer_text == "Test answer"
        assert result.resolved_symbol == "THYAO"
        assert result.retrieval.retrieval_confidence == 0.8

    def test_pipeline_result_with_empty_sources(self):
        response = RAGResponse(
            answer_text="No sources",
            sources=[],
            stock_symbol=None,
            document_type=DocumentType.ANY,
            insufficient_context=True,
        )
        understanding = QueryUnderstandingResult(
            normalized_query="test",
            candidate_symbol=None,
            document_type=DocumentType.ANY,
            intent=QueryIntent.GENERIC,
            confidence=0.3,
            suggested_rewrite=None,
        )
        retrieval = RetrievalAgentResult(
            chunks=[],
            sources=[],
            has_sufficient_context=False,
            retrieval_confidence=0.0,
            context_total_chars=0,
        )

        result = ChatPipelineResult(
            response=response,
            understanding=understanding,
            resolved_symbol=None,
            retrieval=retrieval,
            memory_context="",
        )

        assert result.response.insufficient_context is True
        assert result.retrieval.has_sufficient_context is False


class TestSourceDeduplication:
    """Tests for source deduplication in merger."""

    def test_dedupe_sources_by_id_and_url(self):
        source1 = SourceItem(
            kap_report_id=1,
            stock_symbol="THYAO",
            report_title="Report 1",
            published_at=None,
            filing_type="FR",
            source_url="https://kap.org/1",
            chunk_preview="Preview 1",
        )
        source2 = SourceItem(
            kap_report_id=1,
            stock_symbol="THYAO",
            report_title="Report 1",
            published_at=None,
            filing_type="FR",
            source_url="https://kap.org/1",  # Same as source1
            chunk_preview="Preview 2",
        )
        source3 = SourceItem(
            kap_report_id=2,
            stock_symbol="ASELS",
            report_title="Report 2",
            published_at=None,
            filing_type="FR",
            source_url="https://kap.org/2",
            chunk_preview="Preview 3",
        )

        deduped = _dedupe_sources([source1, source2, source3])

        assert len(deduped) == 2
        assert deduped[0] == source1
        assert deduped[1] == source3


class TestMergerTraceOutput:
    """Tests verifying merger produces trace-friendly output."""

    def test_merge_produces_document_type(self):
        source = SourceItem(
            kap_report_id=1,
            stock_symbol="THYAO",
            report_title="Report",
            published_at=None,
            filing_type="FR",
            source_url="https://kap.org/1",
            chunk_preview="Preview",
        )
        text = TextAnalysisResult(
            answer_text="Test",
            key_points=[],
            sources=[source],
            stock_symbol="THYAO",
            document_type=DocumentType.FR,
            insufficient_context=False,
            retrieval_confidence=0.8,
        )
        classification = QueryClassificationResult(
            query_type=QueryType.TEXT_ANALYSIS,
            symbols=["THYAO"],
            needs_text_analysis=True,
            needs_numerical_analysis=False,
            needs_comparison=False,
            needs_chart=False,
            confidence=0.9,
        )

        result = merge_analysis_results(
            classification=classification,
            resolved_symbol="THYAO",
            numerical_result=None,
            text_result=text,
        )

        assert result.document_type == DocumentType.FR

    def test_merge_propagates_insufficient_context(self):
        numerical = NumericalAnalysisResult(
            symbols=["THYAO"],
            metrics=[],
            comparison_table=None,
            chart=None,
            warnings=["Veri yok"],
            data_sources=[],
            insufficient_data=True,
        )
        classification = QueryClassificationResult(
            query_type=QueryType.NUMERICAL_ANALYSIS,
            symbols=["THYAO"],
            needs_text_analysis=False,
            needs_numerical_analysis=True,
            needs_comparison=False,
            needs_chart=False,
            confidence=0.9,
        )

        result = merge_analysis_results(
            classification=classification,
            resolved_symbol="THYAO",
            numerical_result=numerical,
            text_result=None,
        )

        assert result.insufficient_context is True
        assert result.confidence_note is not None
