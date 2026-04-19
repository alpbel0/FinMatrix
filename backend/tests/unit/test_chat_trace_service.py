"""Unit tests for chat trace service."""

from unittest.mock import AsyncMock
from unittest.mock import MagicMock

import pytest

from app.models.chat_trace import ChatTrace
from app.schemas.chat import QueryUnderstandingResult, RAGResponse, RetrievalAgentResult, SourceItem
from app.schemas.enums import DocumentType, QueryIntent
from app.services.chat_trace_service import (
    ChatPipelineResult,
    create_chat_trace,
    finalize_chat_trace_failure,
    finalize_chat_trace_success,
)


class TestCreateChatTrace:
    @pytest.mark.asyncio
    async def test_create_chat_trace(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        trace = await create_chat_trace(
            db=db,
            session_id=1,
            user_id=2,
            user_message_id=3,
            original_query="THYAO faaliyet raporu ne diyor?",
        )

        assert trace.session_id == 1
        assert trace.user_id == 2
        assert trace.user_message_id == 3
        assert trace.original_query == "THYAO faaliyet raporu ne diyor?"
        assert trace.status == "STARTED"


class TestFinalizeChatTrace:
    @staticmethod
    def _pipeline_result() -> ChatPipelineResult:
        return ChatPipelineResult(
            response=RAGResponse(
                answer_text="THYAO faaliyet raporunda sürdürülebilirlik vurgulanıyor.",
                sources=[
                    SourceItem(
                        kap_report_id=211,
                        stock_symbol="THYAO",
                        report_title="Faaliyet Raporu (Konsolide)",
                        published_at=None,
                        filing_type="FAR",
                        source_url="https://www.kap.org.tr/tr/Bildirim/1566094",
                        chunk_preview="KAP'ta yayınlanma tarihi...",
                    )
                ],
                stock_symbol="THYAO",
                document_type=DocumentType.FAR,
                confidence_note=None,
                insufficient_context=False,
            ),
            understanding=QueryUnderstandingResult(
                normalized_query="THYAO faaliyet raporu ne diyor",
                candidate_symbol="THYAO",
                document_type=DocumentType.FAR,
                intent=QueryIntent.SUMMARY,
                confidence=0.8,
            ),
            resolved_symbol="THYAO",
            retrieval=RetrievalAgentResult(
                chunks=[
                    {
                        "chunk_text": "KAP'ta yayınlanma tarihi ve saati...",
                        "score": 0.42,
                        "metadata": {
                            "kap_report_id": 211,
                            "stock_symbol": "THYAO",
                            "filing_type": "FAR",
                            "source_url": "https://www.kap.org.tr/tr/Bildirim/1566094",
                        },
                    }
                ],
                sources=[
                    SourceItem(
                        kap_report_id=211,
                        stock_symbol="THYAO",
                        report_title="Faaliyet Raporu (Konsolide)",
                        published_at=None,
                        filing_type="FAR",
                        source_url="https://www.kap.org.tr/tr/Bildirim/1566094",
                        chunk_preview="KAP'ta yayınlanma tarihi...",
                    )
                ],
                has_sufficient_context=True,
                retrieval_confidence=0.82,
                context_total_chars=980,
            ),
            memory_context="Kullanıcı: Önceki soru",
        )

    @pytest.mark.asyncio
    async def test_finalize_success(self):
        db = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        trace = ChatTrace(
            session_id=1,
            user_id=2,
            user_message_id=3,
            original_query="THYAO faaliyet raporu ne diyor?",
            status="STARTED",
        )

        result = await finalize_chat_trace_success(
            db=db,
            trace=trace,
            pipeline_result=self._pipeline_result(),
            assistant_message_id=4,
            duration_ms=1234,
        )

        assert result.status == "SUCCESS"
        assert result.assistant_message_id == 4
        assert result.resolved_symbol == "THYAO"
        assert result.document_type == "FAR"
        assert result.intent == "summary"
        assert result.retrieved_chunk_count == 1
        assert result.has_sufficient_context is True
        assert result.duration_ms == 1234
        assert result.sources_metadata[0]["kap_report_id"] == 211

    @pytest.mark.asyncio
    async def test_finalize_failure(self):
        db = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        trace = ChatTrace(
            session_id=1,
            user_id=2,
            user_message_id=3,
            original_query="THYAO faaliyet raporu ne diyor?",
            status="STARTED",
        )

        result = await finalize_chat_trace_failure(
            db=db,
            trace=trace,
            error_message="OpenRouter timeout",
            duration_ms=456,
            pipeline_result=self._pipeline_result(),
        )

        assert result.status == "FAILED"
        assert result.error_message == "OpenRouter timeout"
        assert result.duration_ms == 456
        assert result.intent == "summary"
        assert result.retrieved_chunk_count == 1
