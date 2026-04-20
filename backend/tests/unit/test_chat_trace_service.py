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
        assert result.graph_node_history == []
        assert result.graph_fallback_reason is None

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
        assert result.graph_node_history == []
        assert result.graph_fallback_reason is None

    @pytest.mark.asyncio
    async def test_finalize_persists_graph_debug_fields(self):
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
        pipeline_result = self._pipeline_result()
        pipeline_result.node_history = [
            {
                "node": "classify_query",
                "status": "ok",
                "duration_ms": 12.5,
                "reason_code": None,
            },
            {
                "node": "fallback",
                "status": "ok",
                "duration_ms": 40.0,
                "reason_code": "classification_failed",
            },
        ]
        pipeline_result.fallback_reason = "classification_failed"

        result = await finalize_chat_trace_success(
            db=db,
            trace=trace,
            pipeline_result=pipeline_result,
            assistant_message_id=4,
            duration_ms=1234,
        )

        assert result.graph_node_history == pipeline_result.node_history
        assert result.graph_fallback_reason == "classification_failed"

    @pytest.mark.asyncio
    async def test_finalize_failure_handles_missing_response(self):
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
        pipeline_result = self._pipeline_result()
        pipeline_result.response = None
        pipeline_result.node_history = [
            {
                "node": "merge",
                "status": "error",
                "duration_ms": 9.0,
                "reason_code": "merge_failed",
            }
        ]
        pipeline_result.fallback_reason = "merge_failed"

        result = await finalize_chat_trace_failure(
            db=db,
            trace=trace,
            error_message="Chat pipeline returned no response",
            duration_ms=456,
            pipeline_result=pipeline_result,
        )

        assert result.status == "FAILED"
        assert result.graph_node_history == pipeline_result.node_history
        assert result.graph_fallback_reason == "merge_failed"
        assert result.sources_metadata == []
        assert result.response_payload == {}
