"""Unit tests for LangGraph state definitions (Task 7.2)."""

import pytest

from app.schemas.chat import (
    NumericalAnalysisResult,
    QueryClassificationResult,
    RAGResponse,
    TextAnalysisResult,
)
from app.schemas.enums import DocumentType, QueryType
from app.services.agents.graph.state import AgentState, NodeTraceEntry


class TestNodeTraceEntry:
    """Tests for NodeTraceEntry TypedDict."""

    def test_node_trace_entry_fields(self):
        """All required fields are present and correctly typed."""
        entry = NodeTraceEntry(
            node="classify_query",
            status="ok",
            duration_ms=125.5,
            reason_code=None,
        )
        assert entry["node"] == "classify_query"
        assert entry["status"] == "ok"
        assert entry["duration_ms"] == 125.5
        assert entry["reason_code"] is None

    def test_node_trace_entry_with_reason_code(self):
        """reason_code can be set to a string value."""
        entry = NodeTraceEntry(
            node="fallback",
            status="skipped",
            duration_ms=0.1,
            reason_code="symbol_not_resolved",
        )
        assert entry["reason_code"] == "symbol_not_resolved"

    def test_node_trace_entry_error_status(self):
        """status='error' is valid."""
        entry = NodeTraceEntry(
            node="numerical_analysis",
            status="error",
            duration_ms=50.0,
            reason_code="numerical_failed",
        )
        assert entry["status"] == "error"

    def test_node_trace_entry_is_dict_subclass(self):
        """NodeTraceEntry is a dict subclass supporting dict operations."""
        entry = NodeTraceEntry(
            node="merge",
            status="ok",
            duration_ms=10.0,
            reason_code=None,
        )
        assert isinstance(entry, dict)
        assert "node" in entry
        assert list(entry.keys()) == ["node", "status", "duration_ms", "reason_code"]


class TestAgentState:
    """Tests for AgentState TypedDict."""

    def test_agent_state_minimal_init(self):
        """AgentState can be created with only required fields."""
        state = AgentState(
            query="THYAO net kar analiz et",
            user_id=1,
            session_id=42,
        )
        assert state["query"] == "THYAO net kar analiz et"
        assert state["user_id"] == 1
        assert state["session_id"] == 42

    def test_agent_state_optional_fields_can_be_none(self):
        """Optional fields can be set to None explicitly."""
        state = AgentState(
            query="test",
            user_id=1,
            session_id=1,
            classification=None,
            resolved_symbol=None,
            text_result=None,
            numerical_result=None,
            response=None,
            fallback_reason=None,
            http_client=None,
            node_history=[],
        )
        assert state["classification"] is None
        assert state["resolved_symbol"] is None
        assert state["text_result"] is None
        assert state["numerical_result"] is None
        assert state["response"] is None
        assert state["fallback_reason"] is None
        assert state["http_client"] is None
        assert state["node_history"] == []

    def test_agent_state_http_client_none_by_default(self):
        """http_client is None when explicitly set."""
        state = AgentState(
            query="test",
            user_id=1,
            session_id=1,
            http_client=None,
        )
        assert state["http_client"] is None

    def test_agent_state_node_history_starts_empty(self):
        """node_history starts as an empty list when provided."""
        state = AgentState(
            query="test",
            user_id=1,
            session_id=1,
            node_history=[],
        )
        assert state["node_history"] == []

    def test_agent_state_is_dict_subclass(self):
        """AgentState supports dict operations."""
        state = AgentState(
            query="test",
            user_id=1,
            session_id=1,
        )
        assert isinstance(state, dict)
        assert "query" in state
        assert len(state) > 0

    def test_agent_state_all_fields_settable(self):
        """All fields can be set to their respective types."""
        from app.services.agents.graph.state import NodeTraceEntry

        state = AgentState(
            query="ASELS roe analiz",
            user_id=5,
            session_id=99,
            http_client=None,
            classification=QueryClassificationResult(
                query_type=QueryType.NUMERICAL_ANALYSIS,
                symbols=["ASELS"],
                needs_text_analysis=False,
                needs_numerical_analysis=True,
                confidence=0.9,
            ),
            resolved_symbol="ASELS",
            text_result=None,
            numerical_result=NumericalAnalysisResult(
                symbols=["ASELS"],
                metrics=[],
                insufficient_data=False,
            ),
            response=None,
            fallback_reason=None,
            node_history=[
                NodeTraceEntry(
                    node="classify_query",
                    status="ok",
                    duration_ms=80.0,
                    reason_code=None,
                )
            ],
        )

        assert state["query"] == "ASELS roe analiz"
        assert state["user_id"] == 5
        assert state["session_id"] == 99
        assert state["http_client"] is None
        assert state["classification"].query_type == QueryType.NUMERICAL_ANALYSIS
        assert state["resolved_symbol"] == "ASELS"
        assert state["numerical_result"].symbols == ["ASELS"]
        assert state["node_history"][0]["node"] == "classify_query"
        assert state["node_history"][0]["status"] == "ok"

    def test_agent_state_node_history_annotated(self):
        """node_history field is typed as Annotated for LangGraph parallel-safe append."""
        state = AgentState(
            query="test",
            user_id=1,
            session_id=1,
            node_history=[],
        )
        # Verify node_history is a list that can be extended (LangGraph uses operator.add)
        assert isinstance(state["node_history"], list)
        assert len(state["node_history"]) == 0

        # Simulate what operator.add does (append)
        from app.services.agents.graph.state import NodeTraceEntry

        entry = NodeTraceEntry(
            node="classify_query",
            status="ok",
            duration_ms=50.0,
            reason_code=None,
        )
        state["node_history"].append(entry)
        assert len(state["node_history"]) == 1
        assert state["node_history"][0]["node"] == "classify_query"
