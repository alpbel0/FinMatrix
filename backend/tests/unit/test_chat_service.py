"""Unit tests for chat service message flow."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.chat import (
    QueryUnderstandingResult,
    RetrievalAgentResult,
)
from app.schemas.enums import DocumentType, QueryIntent
from app.services.chat_service import send_message
from app.services.chat_trace_service import ChatPipelineResult


def _pipeline_result_without_response() -> ChatPipelineResult:
    return ChatPipelineResult(
        response=None,
        understanding=QueryUnderstandingResult(
            normalized_query="THYAO analiz",
            candidate_symbol="THYAO",
            document_type=DocumentType.FR,
            intent=QueryIntent.SUMMARY,
            confidence=0.7,
        ),
        resolved_symbol="THYAO",
        retrieval=RetrievalAgentResult(
            chunks=[],
            sources=[],
            has_sufficient_context=False,
            retrieval_confidence=0.0,
            context_total_chars=0,
        ),
        memory_context="",
        node_history=[
            {
                "node": "merge",
                "status": "error",
                "duration_ms": 8.0,
                "reason_code": "merge_failed",
            }
        ],
        fallback_reason="merge_failed",
    )


class TestSendMessage:
    @pytest.mark.asyncio
    async def test_send_message_fails_fast_when_pipeline_response_missing(self):
        db = AsyncMock()
        trace = MagicMock()
        user_message = MagicMock(id=11)

        with patch(
            "app.services.chat_service.save_message",
            new_callable=AsyncMock,
            side_effect=[user_message],
        ), patch(
            "app.services.chat_service.create_chat_trace",
            new_callable=AsyncMock,
            return_value=trace,
        ), patch(
            "app.services.chat_service.run_chat_pipeline",
            new_callable=AsyncMock,
            return_value=_pipeline_result_without_response(),
        ), patch(
            "app.services.chat_service.finalize_chat_trace_failure",
            new_callable=AsyncMock,
        ) as mock_finalize_failure:
            with pytest.raises(RuntimeError, match="Chat pipeline returned no response"):
                await send_message(
                    db=db,
                    user_id=1,
                    session_id=2,
                    message="THYAO analiz et",
                )

        db.rollback.assert_awaited_once()
        mock_finalize_failure.assert_awaited_once()
        failure_call = mock_finalize_failure.await_args.kwargs
        assert failure_call["pipeline_result"].fallback_reason == "merge_failed"
        assert failure_call["pipeline_result"].node_history[0]["reason_code"] == "merge_failed"
