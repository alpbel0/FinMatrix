"""Unit tests for direct text analyst flow."""

from unittest.mock import AsyncMock, patch

import pytest

from app.schemas.chat import QueryClassificationResult, RAGResponse, RetrievalAgentResult, SourceItem
from app.schemas.enums import DocumentType, QueryType
from app.services.agents.text_analyst import run_text_analysis


def make_classification(confidence: float = 0.9) -> QueryClassificationResult:
    return QueryClassificationResult(
        query_type=QueryType.TEXT_ANALYSIS,
        symbols=["THYAO"],
        needs_text_analysis=True,
        needs_numerical_analysis=False,
        needs_comparison=False,
        needs_chart=False,
        confidence=confidence,
    )


def make_retrieval(has_sufficient_context: bool = True) -> RetrievalAgentResult:
    source = SourceItem(
        kap_report_id=1,
        stock_symbol="THYAO",
        report_title="THYAO Faaliyet Raporu",
        published_at=None,
        filing_type="FAR",
        source_url="https://kap.example/1",
        chunk_preview="THYAO rapor özeti",
    )
    return RetrievalAgentResult(
        chunks=[{"chunk_text": "THYAO güçlü büyüme gösterdi.", "score": 0.2, "metadata": {"kap_report_id": 1}}],
        sources=[source],
        has_sufficient_context=has_sufficient_context,
        retrieval_confidence=0.82,
        context_total_chars=920,
    )


def make_response(insufficient_context: bool = False) -> RAGResponse:
    return RAGResponse(
        answer_text="THYAO güçlü bir performans sergiliyor.",
        sources=make_retrieval().sources,
        stock_symbol="THYAO",
        document_type=DocumentType.FAR,
        confidence_note="Bazi veriler eksik.",
        insufficient_context=insufficient_context,
    )


@pytest.mark.asyncio
async def test_text_analysis_uses_pre_resolved_symbol():
    retrieval = make_retrieval()
    response = make_response()

    with patch("app.services.agents.text_analyst.get_last_messages", AsyncMock(return_value=[])), \
         patch("app.services.agents.text_analyst.format_memory_context", return_value=""), \
         patch("app.services.agents.text_analyst.run_retrieval", AsyncMock(return_value=retrieval)) as mock_retrieval, \
         patch("app.services.agents.text_analyst.enrich_retrieval_sources", AsyncMock(side_effect=lambda db, r: r)), \
         patch("app.services.agents.text_analyst.get_structured_financial_context", AsyncMock(return_value="")), \
         patch("app.services.agents.text_analyst.generate_response", AsyncMock(return_value=response)):
        result = await run_text_analysis(
            db=AsyncMock(),
            user_id=1,
            session_id=10,
            query="THYAO faaliyet raporu ne diyor?",
            resolved_symbols=["THYAO"],
            classification=make_classification(),
        )

    assert result.stock_symbol == "THYAO"
    mock_retrieval.assert_awaited_once()
    assert mock_retrieval.await_args.kwargs["resolved_symbol"] == "THYAO"


@pytest.mark.asyncio
async def test_text_analysis_bypasses_document_pipeline():
    retrieval = make_retrieval()
    response = make_response()

    with patch("app.services.agents.text_analyst.get_last_messages", AsyncMock(return_value=[])), \
         patch("app.services.agents.text_analyst.format_memory_context", return_value=""), \
         patch("app.services.agents.text_analyst.run_retrieval", AsyncMock(return_value=retrieval)), \
         patch("app.services.agents.text_analyst.enrich_retrieval_sources", AsyncMock(side_effect=lambda db, r: r)), \
         patch("app.services.agents.text_analyst.get_structured_financial_context", AsyncMock(return_value="")), \
         patch("app.services.agents.text_analyst.generate_response", AsyncMock(return_value=response)), \
         patch("app.services.agents.text_analyst.run_document_pipeline", AsyncMock(), create=True) as mock_document_pipeline:
        result = await run_text_analysis(
            db=AsyncMock(),
            user_id=1,
            session_id=10,
            query="THYAO faaliyet raporu ne diyor?",
            resolved_symbols=["THYAO"],
            classification=make_classification(),
        )

    assert result.answer_text == response.answer_text
    mock_document_pipeline.assert_not_called()


@pytest.mark.asyncio
async def test_text_analysis_propagates_insufficient_context():
    retrieval = make_retrieval(has_sufficient_context=False)
    response = make_response(insufficient_context=True)

    with patch("app.services.agents.text_analyst.get_last_messages", AsyncMock(return_value=[])), \
         patch("app.services.agents.text_analyst.format_memory_context", return_value=""), \
         patch("app.services.agents.text_analyst.run_retrieval", AsyncMock(return_value=retrieval)), \
         patch("app.services.agents.text_analyst.enrich_retrieval_sources", AsyncMock(side_effect=lambda db, r: r)), \
         patch("app.services.agents.text_analyst.get_structured_financial_context", AsyncMock(return_value="")), \
         patch("app.services.agents.text_analyst.generate_response", AsyncMock(return_value=response)):
        result = await run_text_analysis(
            db=AsyncMock(),
            user_id=1,
            session_id=10,
            query="THYAO faaliyet raporu ne diyor?",
            resolved_symbols=["THYAO"],
            classification=make_classification(),
        )

    assert result.insufficient_context is True
    assert result.retrieval_confidence == retrieval.retrieval_confidence


@pytest.mark.asyncio
async def test_text_analysis_preserves_sources():
    retrieval = make_retrieval()
    response = make_response()

    with patch("app.services.agents.text_analyst.get_last_messages", AsyncMock(return_value=[])), \
         patch("app.services.agents.text_analyst.format_memory_context", return_value=""), \
         patch("app.services.agents.text_analyst.run_retrieval", AsyncMock(return_value=retrieval)), \
         patch("app.services.agents.text_analyst.enrich_retrieval_sources", AsyncMock(side_effect=lambda db, r: r)), \
         patch("app.services.agents.text_analyst.get_structured_financial_context", AsyncMock(return_value="")), \
         patch("app.services.agents.text_analyst.generate_response", AsyncMock(return_value=response)):
        result = await run_text_analysis(
            db=AsyncMock(),
            user_id=1,
            session_id=10,
            query="THYAO faaliyet raporu ne diyor?",
            resolved_symbols=["THYAO"],
            classification=make_classification(),
        )

    assert len(result.sources) == 1
    assert result.sources[0].stock_symbol == "THYAO"


@pytest.mark.asyncio
async def test_text_analysis_closes_owned_http_client():
    retrieval = make_retrieval()
    response = make_response()
    mock_client = AsyncMock()
    mock_client.aclose = AsyncMock()

    with patch("app.services.agents.text_analyst.httpx.AsyncClient", return_value=mock_client), \
         patch("app.services.agents.text_analyst.get_last_messages", AsyncMock(return_value=[])), \
         patch("app.services.agents.text_analyst.format_memory_context", return_value=""), \
         patch("app.services.agents.text_analyst.run_retrieval", AsyncMock(return_value=retrieval)), \
         patch("app.services.agents.text_analyst.enrich_retrieval_sources", AsyncMock(side_effect=lambda db, r: r)), \
         patch("app.services.agents.text_analyst.get_structured_financial_context", AsyncMock(return_value="")), \
         patch("app.services.agents.text_analyst.generate_response", AsyncMock(return_value=response)):
        await run_text_analysis(
            db=AsyncMock(),
            user_id=1,
            session_id=10,
            query="THYAO faaliyet raporu ne diyor?",
            resolved_symbols=["THYAO"],
            classification=make_classification(),
            http_client=None,
        )

    mock_client.aclose.assert_awaited_once()
