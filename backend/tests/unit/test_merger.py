"""Unit tests for multi-agent results merger."""

from app.schemas.chat import (
    FinancialMetricSnapshot,
    NumericalAnalysisResult,
    QueryClassificationResult,
    SourceItem,
    TextAnalysisResult,
)
from app.schemas.enums import DocumentType, QueryType
from app.services.agents.merger import merge_analysis_results
from app.services.data.provider_models import PeriodType


def _classification(*, needs_text: bool, needs_numerical: bool) -> QueryClassificationResult:
    return QueryClassificationResult(
        query_type=QueryType.COMPARISON if needs_text and needs_numerical else (
            QueryType.NUMERICAL_ANALYSIS if needs_numerical else QueryType.TEXT_ANALYSIS
        ),
        symbols=["THYAO"],
        needs_text_analysis=needs_text,
        needs_numerical_analysis=needs_numerical,
        needs_comparison=needs_text and needs_numerical,
        needs_chart=False,
        confidence=0.9,
    )


class TestMergeAnalysisResults:
    def test_merges_numerical_then_text(self):
        numerical = NumericalAnalysisResult(
            symbols=["THYAO"],
            metrics=[
                FinancialMetricSnapshot(
                    symbol="THYAO",
                    period_type=PeriodType.ANNUAL,
                    statement_date="2025-12-31",
                    net_income=100.0,
                    roe=0.25,
                    source="borsapy",
                )
            ],
            warnings=[],
            data_sources=["income_statements"],
            insufficient_data=False,
        )
        source = SourceItem(
            kap_report_id=1,
            stock_symbol="THYAO",
            report_title="Report",
            published_at=None,
            filing_type="FR",
            source_url="https://kap/1",
            chunk_preview="Preview",
        )
        text = TextAnalysisResult(
            answer_text="Belge bazli risk analizi.",
            key_points=["Likidite riski vurgulaniyor."],
            sources=[source],
            stock_symbol="THYAO",
            document_type=DocumentType.FR,
            insufficient_context=False,
            retrieval_confidence=0.8,
        )

        result = merge_analysis_results(
            classification=_classification(needs_text=True, needs_numerical=True),
            resolved_symbol="THYAO",
            numerical_result=numerical,
            text_result=text,
        )

        assert "THYAO" in result.answer_text
        assert "---" in result.answer_text
        assert "Belge bazli risk analizi." in result.answer_text
        assert result.sources == [source]
        assert result.stock_symbol == "THYAO"

    def test_dedupes_sources(self):
        source = SourceItem(
            kap_report_id=1,
            stock_symbol="THYAO",
            report_title="Report",
            published_at=None,
            filing_type="FR",
            source_url="https://kap/1",
            chunk_preview="Preview",
        )
        text = TextAnalysisResult(
            answer_text="Test",
            key_points=[],
            sources=[source, source],
            stock_symbol="THYAO",
            document_type=DocumentType.FR,
            insufficient_context=False,
            retrieval_confidence=0.8,
        )

        result = merge_analysis_results(
            classification=_classification(needs_text=True, needs_numerical=False),
            resolved_symbol="THYAO",
            numerical_result=None,
            text_result=text,
        )

        assert len(result.sources) == 1

    def test_marks_insufficient_for_numerical_only_failure(self):
        numerical = NumericalAnalysisResult(
            symbols=["THYAO"],
            metrics=[],
            comparison_table=None,
            chart=None,
            warnings=["Finansal veri yok"],
            data_sources=["income_statements"],
            insufficient_data=True,
        )

        result = merge_analysis_results(
            classification=_classification(needs_text=False, needs_numerical=True),
            resolved_symbol="THYAO",
            numerical_result=numerical,
            text_result=None,
        )

        assert result.insufficient_context is True
        assert result.confidence_note is not None

    def test_numerical_only_no_text(self):
        """Test merge when only numerical analysis is available."""
        numerical = NumericalAnalysisResult(
            symbols=["THYAO"],
            metrics=[
                FinancialMetricSnapshot(
                    symbol="THYAO",
                    period_type=PeriodType.ANNUAL,
                    statement_date="2025-12-31",
                    net_income=150.0,
                    roe=0.22,
                    source="borsapy",
                )
            ],
            warnings=[],
            data_sources=["income_statements"],
            insufficient_data=False,
        )

        result = merge_analysis_results(
            classification=_classification(needs_text=False, needs_numerical=True),
            resolved_symbol="THYAO",
            numerical_result=numerical,
            text_result=None,
        )

        assert "THYAO" in result.answer_text
        assert "Net Kar" in result.answer_text
        assert result.stock_symbol == "THYAO"
        assert result.sources == []

    def test_text_only_no_numerical(self):
        """Test merge when only text analysis is available."""
        source = SourceItem(
            kap_report_id=1,
            stock_symbol="ASELS",
            report_title="ASELS Report",
            published_at=None,
            filing_type="FAR",
            source_url="https://kap.org/1",
            chunk_preview="Preview text",
        )
        text = TextAnalysisResult(
            answer_text="ASELS faaliyet raporu analizi tamamlandi.",
            key_points=["Onemli bulgu 1", "Onemli bulgu 2"],
            sources=[source],
            stock_symbol="ASELS",
            document_type=DocumentType.FAR,
            insufficient_context=False,
            retrieval_confidence=0.82,
        )

        result = merge_analysis_results(
            classification=_classification(needs_text=True, needs_numerical=False),
            resolved_symbol="ASELS",
            numerical_result=None,
            text_result=text,
        )

        assert "ASELS" in result.answer_text
        assert "Belge Bazli Analiz" in result.answer_text
        assert result.sources == [source]

    def test_empty_answer_parts_handling(self):
        """Test handling when both results produce empty content."""
        numerical = NumericalAnalysisResult(
            symbols=["THYAO"],
            metrics=[],
            comparison_table=None,
            chart=None,
            warnings=[],
            data_sources=[],
            insufficient_data=True,
        )

        result = merge_analysis_results(
            classification=_classification(needs_text=False, needs_numerical=True),
            resolved_symbol="THYAO",
            numerical_result=numerical,
            text_result=None,
        )

        # Should still produce some output, not empty
        assert result.answer_text != ""
        assert result.insufficient_context is True
