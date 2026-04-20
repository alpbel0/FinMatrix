"""Tests for the LangGraph-based orchestrator refactor (Task 7.6)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.agents.orchestrator import (
    _build_minimal_understanding,
    _empty_retrieval,
    _log_graph_summary,
    build_orchestrator_agent,
    get_orchestrator_agent,
    run_orchestrated_pipeline,
)
from app.services.chat_trace_service import ChatPipelineResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_rag_response():
    from app.schemas.chat import RAGResponse, SourceItem
    from app.schemas.enums import DocumentType

    return RAGResponse(
        answer_text="THYAO 2024 yılında 245.8 milyar TL gelir elde etti.",
        sources=[
            SourceItem(
                kap_report_id=1,
                stock_symbol="THYAO",
                report_title="THYAO 2024 Yıllık Faaliyet Raporu",
                published_at="2024-03-15",
                filing_type="FR",
                source_url="https://kap.gov.tr/...",
                chunk_preview="THYAO gelirleri...",
            )
        ],
        stock_symbol="THYAO",
        document_type=DocumentType.FR,
        confidence_note=None,
        insufficient_context=False,
        chart=None,
        comparison_table=None,
    )


def _make_mock_graph(overrides: dict | None = None):
    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock()
    mock_graph.ainvoke.return_value = {
        "query": "THYAO 2024 geliri ne kadar?",
        "user_id": 1,
        "session_id": 2,
        "http_client": None,
        "node_history": [
            {"node": "classify_query", "status": "ok", "duration_ms": 120.0, "reason_code": None},
            {"node": "resolve_symbol", "status": "ok", "duration_ms": 30.0, "reason_code": None},
            {"node": "text_analysis", "status": "ok", "duration_ms": 800.0, "reason_code": None},
        ],
        "classification": None,
        "resolved_symbol": "THYAO",
        "text_result": None,
        "numerical_result": None,
        "response": _make_mock_rag_response(),
        "fallback_reason": None,
        **(overrides or {}),
    }
    return mock_graph


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRunOrchestratedPipelineCallsGraph:
    """Verify run_orchestrated_pipeline delegates to the LangGraph."""

    @pytest.mark.asyncio
    async def test_run_orchestrated_pipeline_calls_graph_ainvoke(self):
        """graph.ainvoke is called exactly once with the correct initial state."""
        mock_graph = _make_mock_graph()

        with patch("app.services.agents.orchestrator.get_graph", return_value=mock_graph):
            await run_orchestrated_pipeline(
                db=MagicMock(spec=AsyncSession),
                user_id=1,
                session_id=2,
                query="THYAO 2024 geliri ne kadar?",
                http_client=None,
            )

        mock_graph.ainvoke.assert_called_once()
        call_args = mock_graph.ainvoke.call_args
        initial_state = call_args[0][0]

        assert initial_state["query"] == "THYAO 2024 geliri ne kadar?"
        assert initial_state["user_id"] == 1
        assert initial_state["session_id"] == 2
        assert initial_state["http_client"] is None
        assert initial_state["node_history"] == []

    @pytest.mark.asyncio
    async def test_initial_state_does_not_include_db(self):
        """DB session is NOT placed into the graph state (nodes create their own)."""
        mock_graph = _make_mock_graph()

        with patch("app.services.agents.orchestrator.get_graph", return_value=mock_graph):
            await run_orchestrated_pipeline(
                db=MagicMock(spec=AsyncSession),
                user_id=1,
                session_id=2,
                query="THYAO 2024 geliri ne kadar?",
                http_client=None,
            )

        initial_state = mock_graph.ainvoke.call_args[0][0]
        assert "db" not in initial_state


class TestRunOrchestratedPipelineReturns:
    """Verify return value structure."""

    @pytest.mark.asyncio
    async def test_run_orchestrated_pipeline_returns_chat_pipeline_result(self):
        """Return type is ChatPipelineResult."""
        mock_graph = _make_mock_graph()

        with patch("app.services.agents.orchestrator.get_graph", return_value=mock_graph):
            result = await run_orchestrated_pipeline(
                db=MagicMock(spec=AsyncSession),
                user_id=1,
                session_id=2,
                query="THYAO 2024 geliri ne kadar?",
                http_client=None,
            )

        assert isinstance(result, ChatPipelineResult)

    @pytest.mark.asyncio
    async def test_response_extracted_from_final_state(self):
        """final_state['response'] becomes ChatPipelineResult.response."""
        mock_response = _make_mock_rag_response()
        mock_graph = _make_mock_graph({"response": mock_response})

        with patch("app.services.agents.orchestrator.get_graph", return_value=mock_graph):
            result = await run_orchestrated_pipeline(
                db=MagicMock(spec=AsyncSession),
                user_id=1,
                session_id=2,
                query="THYAO 2024 geliri ne kadar?",
                http_client=None,
            )

        assert result.response is mock_response

    @pytest.mark.asyncio
    async def test_resolved_symbol_extracted_from_final_state(self):
        """final_state['resolved_symbol'] becomes ChatPipelineResult.resolved_symbol."""
        mock_graph = _make_mock_graph({"resolved_symbol": "ASELS"})

        with patch("app.services.agents.orchestrator.get_graph", return_value=mock_graph):
            result = await run_orchestrated_pipeline(
                db=MagicMock(spec=AsyncSession),
                user_id=1,
                session_id=2,
                query="ASELS borçluluk oranı nedir?",
                http_client=None,
            )

        assert result.resolved_symbol == "ASELS"

    @pytest.mark.asyncio
    async def test_response_none_handled_gracefully(self):
        """When graph returns response=None, ChatPipelineResult still builds (no crash)."""
        mock_graph = _make_mock_graph({"response": None, "resolved_symbol": None})

        with patch("app.services.agents.orchestrator.get_graph", return_value=mock_graph):
            result = await run_orchestrated_pipeline(
                db=MagicMock(spec=AsyncSession),
                user_id=1,
                session_id=2,
                query="hava nasıl?",
                http_client=None,
            )

        assert result.response is None
        assert result.understanding is not None


class TestNodeHistoryLogging:
    """Verify node_history is logged via _log_graph_summary."""

    @pytest.mark.asyncio
    async def test_node_history_passed_to_log_summary(self):
        """_log_graph_summary is called with the node_history from final_state."""
        node_history = [
            {"node": "classify_query", "status": "ok", "duration_ms": 100.0, "reason_code": None},
            {"node": "resolve_symbol", "status": "ok", "duration_ms": 40.0, "reason_code": None},
        ]
        mock_graph = _make_mock_graph({"node_history": node_history})

        with patch("app.services.agents.orchestrator.get_graph", return_value=mock_graph):
            with patch("app.services.agents.orchestrator._log_graph_summary") as mock_log:
                await run_orchestrated_pipeline(
                    db=MagicMock(spec=AsyncSession),
                    user_id=1,
                    session_id=2,
                    query="THYAO geliri?",
                    http_client=None,
                )

                mock_log.assert_called_once()
                call_args = mock_log.call_args
                assert call_args[0][0] == node_history

    @pytest.mark.asyncio
    async def test_fallback_reason_passed_to_summary(self):
        """fallback_reason from final_state is passed to _log_graph_summary."""
        mock_graph = _make_mock_graph({"fallback_reason": "no_symbol_resolved"})

        with patch("app.services.agents.orchestrator.get_graph", return_value=mock_graph):
            with patch("app.services.agents.orchestrator._log_graph_summary") as mock_log:
                await run_orchestrated_pipeline(
                    db=MagicMock(spec=AsyncSession),
                    user_id=1,
                    session_id=2,
                    query="foobar",
                    http_client=None,
                )

                mock_log.assert_called_once()
                call_args = mock_log.call_args
                assert call_args[0][1] == "no_symbol_resolved"

    @pytest.mark.asyncio
    async def test_graph_debug_fields_preserved_in_pipeline_result(self):
        """node_history and fallback_reason are preserved for trace persistence."""
        node_history = [
            {"node": "classify_query", "status": "ok", "duration_ms": 100.0, "reason_code": None},
            {"node": "fallback", "status": "ok", "duration_ms": 250.0, "reason_code": "classification_failed"},
        ]
        mock_graph = _make_mock_graph(
            {"node_history": node_history, "fallback_reason": "classification_failed"}
        )

        with patch("app.services.agents.orchestrator.get_graph", return_value=mock_graph):
            result = await run_orchestrated_pipeline(
                db=MagicMock(spec=AsyncSession),
                user_id=1,
                session_id=2,
                query="THYAO geliri ne kadar?",
                http_client=None,
            )

        assert result.node_history == node_history
        assert result.fallback_reason == "classification_failed"

    @pytest.mark.asyncio
    async def test_empty_node_history_handled(self):
        """node_history=[] does not crash _log_graph_summary."""
        mock_graph = _make_mock_graph({"node_history": []})

        with patch("app.services.agents.orchestrator.get_graph", return_value=mock_graph):
            with patch("app.services.agents.orchestrator._log_graph_summary") as mock_log:
                await run_orchestrated_pipeline(
                    db=MagicMock(spec=AsyncSession),
                    user_id=1,
                    session_id=2,
                    query="merhaba",
                    http_client=None,
                )

                mock_log.assert_called_once()
                call_args = mock_log.call_args
                assert call_args[0][0] == []
                assert call_args[0][1] is None

    @pytest.mark.asyncio
    async def test_log_graph_summary_computes_total_duration(self):
        """_log_graph_summary logs node_count and total_duration_ms."""
        node_history = [
            {"node": "a", "status": "ok", "duration_ms": 100.0, "reason_code": None},
            {"node": "b", "status": "ok", "duration_ms": 200.0, "reason_code": None},
        ]

        with patch("app.services.agents.orchestrator.logger") as mock_logger:
            _log_graph_summary(node_history, None)

            mock_logger.info.assert_called_once()
            log_call = mock_logger.info.call_args
            # Positional args: (format_string, node_count, total_ms, fallback_reason)
            args = log_call[0]
            assert args[1] == 2   # node_count
            assert args[2] == 300.0  # total_ms


class TestBuildMinimalUnderstanding:
    """Tests for the _build_minimal_understanding helper."""

    def test_build_minimal_understanding_with_response_and_stock_symbol(self):
        """When response has stock_symbol, candidate_symbol is set from it."""
        response = _make_mock_rag_response()
        result = _build_minimal_understanding(response, "THYAO geliri ne?")

        assert result.candidate_symbol == "THYAO"
        assert result.normalized_query == "THYAO geliri ne?"
        assert result.confidence == 1.0

    def test_build_minimal_understanding_without_response(self):
        """When response is None, all fields are minimal defaults."""
        result = _build_minimal_understanding(None, "hava nasıl?")

        assert result.candidate_symbol is None
        assert result.normalized_query == "hava nasıl?"
        assert result.confidence == 0.0
        assert result.intent.value == "generic"

    def test_build_minimal_understanding_with_response_no_symbol(self):
        """When response exists but has no stock_symbol, returns GENERIC intent."""
        from app.schemas.chat import RAGResponse
        from app.schemas.enums import DocumentType

        response = RAGResponse(
            answer_text="Merhaba!",
            sources=[],
            stock_symbol=None,
            document_type=DocumentType.ANY,
            confidence_note=None,
            insufficient_context=False,
            chart=None,
            comparison_table=None,
        )
        result = _build_minimal_understanding(response, "merhaba")

        assert result.candidate_symbol is None
        assert result.intent.value == "generic"


class TestBackwardCompatibility:
    """Verify backward-compatible functions still exist."""

    def test_build_orchestrator_agent_is_callable(self):
        """build_orchestrator_agent() exists and is callable (no crash on import)."""
        result = build_orchestrator_agent()
        # Returns CrewAI agent spec or metadata dict — we just verify it doesn't raise
        assert result is not None

    def test_get_orchestrator_agent_is_callable(self):
        """get_orchestrator_agent() is callable and returns the same instance."""
        get_orchestrator_agent.cache_clear()
        result = get_orchestrator_agent()
        assert result is not None
        # Second call returns same instance (cached)
        result2 = get_orchestrator_agent()
        assert result is result2


class TestEmptyRetrieval:
    """Tests for _empty_retrieval helper."""

    def test_empty_retrieval_returns_valid_retrieval_agent_result(self):
        result = _empty_retrieval()
        assert result.has_sufficient_context is False
        assert result.retrieval_confidence == 0.0
        assert result.context_total_chars == 0
        assert result.chunks == []
        assert result.sources == []
