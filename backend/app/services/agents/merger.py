"""Results merger for multi-agent chat responses."""

from app.schemas.chat import (
    NumericalAnalysisResult,
    QueryClassificationResult,
    RAGResponse,
    SourceItem,
    TextAnalysisResult,
)
from app.schemas.enums import DocumentType


def _format_numerical_result(numerical: NumericalAnalysisResult) -> str:
    """Format numerical analysis as a readable text section."""
    parts: list[str] = []

    if numerical.comparison_table:
        parts.append("Sayisal Ozet")
        for row in numerical.comparison_table:
            values_str = " | ".join(
                f"{symbol}: {value:.2f}" if value is not None else f"{symbol}: N/A"
                for symbol, value in row.values.items()
            )
            parts.append(f"- {row.metric}: {values_str}")
        parts.append("")

    for metric in numerical.metrics:
        parts.append(f"{metric.symbol} ({metric.period_type.value} {metric.statement_date})")
        if metric.net_income is not None:
            parts.append(f"- Net Kar: {metric.net_income:,.0f} TRY")
        if metric.revenue is not None:
            parts.append(f"- Hasilat: {metric.revenue:,.0f} TRY")
        if metric.roe is not None:
            parts.append(f"- ROE: {metric.roe:.2%}")
        if metric.pe_ratio is not None:
            parts.append(f"- P/E: {metric.pe_ratio:.2f}")
        if metric.debt_to_equity is not None:
            parts.append(f"- Borc/Ozsermaye: {metric.debt_to_equity:.2f}")
        if metric.net_profit_growth is not None:
            parts.append(f"- Net Kar Buyumesi: {metric.net_profit_growth:.2%}")
        parts.append("")

    if numerical.chart:
        parts.append(numerical.chart.title)
        for series in numerical.chart.series:
            parts.append(f"- Seri: {series.name}")
            for point in series.data:
                date_str = point.get("date", "")
                value = point.get("value")
                if value is not None:
                    parts.append(f"  - {date_str}: {value:,.0f} TRY")

    if numerical.warnings:
        parts.append("")
        parts.append("Uyarilar")
        for warning in numerical.warnings:
            parts.append(f"- {warning}")

    return "\n".join(part for part in parts if part is not None).strip()


def _format_text_result(text_result: TextAnalysisResult) -> str:
    """Format text analysis as a readable text section."""
    parts: list[str] = []
    if text_result.answer_text:
        parts.append(text_result.answer_text)
    if text_result.key_points:
        parts.append("")
        parts.append("Belge Bazli Analiz")
        for point in text_result.key_points:
            parts.append(f"- {point}")
    return "\n".join(parts).strip()


def _dedupe_sources(sources: list[SourceItem]) -> list[SourceItem]:
    """Deduplicate sources by report id + URL while preserving order."""
    seen: set[tuple[int, str]] = set()
    deduped: list[SourceItem] = []
    for source in sources:
        key = (source.kap_report_id, source.source_url)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(source)
    return deduped


def merge_analysis_results(
    *,
    classification: QueryClassificationResult,
    resolved_symbol: str | None,
    numerical_result: NumericalAnalysisResult | None,
    text_result: TextAnalysisResult | None,
) -> RAGResponse:
    """Merge numerical and text agent outputs into a final response."""
    answer_parts: list[str] = []

    if numerical_result:
        numerical_text = _format_numerical_result(numerical_result)
        if numerical_text:
            answer_parts.append(numerical_text)

    if text_result:
        text_block = _format_text_result(text_result)
        if text_block:
            if answer_parts:
                answer_parts.append("")
                answer_parts.append("---")
                answer_parts.append("")
            answer_parts.append(text_block)

    if not answer_parts:
        answer_parts.append("Bu sorgu icin birlestirilecek analiz sonucu bulunamadi.")

    sources = _dedupe_sources(text_result.sources if text_result else [])
    document_type = text_result.document_type if text_result else DocumentType.ANY

    confidence_note: str | None = None
    if numerical_result and numerical_result.warnings:
        confidence_note = "Bazi finansal veriler eksik veya hesaplanamadi."
    if text_result and text_result.confidence_note:
        confidence_note = text_result.confidence_note

    insufficient_context = False
    if classification.needs_numerical_analysis and numerical_result and numerical_result.insufficient_data:
        insufficient_context = text_result is None
    if text_result and text_result.insufficient_context:
        insufficient_context = True

    return RAGResponse(
        answer_text="\n".join(answer_parts),
        sources=sources,
        stock_symbol=resolved_symbol,
        document_type=document_type,
        confidence_note=confidence_note,
        insufficient_context=insufficient_context,
    )
