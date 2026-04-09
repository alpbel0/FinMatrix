"""Unit tests for chat RAG service.

Tests:
- Process chat query pipeline
- Session management
- Message saving
- Memory context
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.schemas.enums import DocumentType, QueryIntent
from app.schemas.chat import RAGResponse
from app.models.chat import ChatSession, ChatMessage
from app.services.chat_rag_service import (
    create_chat_session,
    enrich_retrieval_sources,
    format_memory_context,
    get_last_messages,
    get_user_sessions,
    process_chat_query,
    save_message,
)


class TestFormatMemoryContext:
    """Tests for format_memory_context function."""

    def test_empty_messages(self):
        """Test empty messages returns empty string."""
        result = format_memory_context([])
        assert result == ""

    def test_single_user_message(self):
        """Test single user message formatting."""
        msg = ChatMessage(
            id=1,
            session_id=1,
            role="user",
            content="Test question",
            sources_metadata=[],
        )
        result = format_memory_context([msg])
        assert "Kullanıcı: Test question" in result

    def test_single_assistant_message(self):
        """Test single assistant message formatting."""
        msg = ChatMessage(
            id=1,
            session_id=1,
            role="assistant",
            content="Test answer",
            sources_metadata=[{"kap_report_id": 1}],
        )
        result = format_memory_context([msg])
        assert "Asistan: Test answer" in result

    def test_multiple_messages(self):
        """Test multiple messages formatting."""
        messages = [
            ChatMessage(id=1, session_id=1, role="user", content="Q1", sources_metadata=[]),
            ChatMessage(id=2, session_id=1, role="assistant", content="A1", sources_metadata=[]),
            ChatMessage(id=3, session_id=1, role="user", content="Q2", sources_metadata=[]),
        ]
        result = format_memory_context(messages)
        assert "Kullanıcı: Q1" in result
        assert "Asistan: A1" in result
        assert "Kullanıcı: Q2" in result

    def test_long_message_truncation(self):
        """Test long message is truncated."""
        long_content = "x" * 500
        msg = ChatMessage(
            id=1,
            session_id=1,
            role="user",
            content=long_content,
            sources_metadata=[],
        )
        result = format_memory_context([msg])
        # Should be truncated to 200 chars
        assert len(result.split(": ")[1]) == 200


class TestGetLastMessages:
    """Tests for get_last_messages function."""

    @pytest.mark.asyncio
    async def test_empty_result(self):
        """Test empty result when no messages."""
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db.execute.return_value = mock_result

        result = await get_last_messages(db, session_id=1, limit=5)

        assert result == []

    @pytest.mark.asyncio
    async def test_returns_messages(self):
        """Test returns messages."""
        db = AsyncMock()
        messages = [
            ChatMessage(id=1, session_id=1, role="user", content="Test", sources_metadata=[]),
        ]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = messages
        db.execute.return_value = mock_result

        result = await get_last_messages(db, session_id=1, limit=5)

        assert len(result) == 1


class TestProcessChatQuery:
    """Tests for process_chat_query function."""

    @pytest.mark.asyncio
    async def test_invalid_session(self):
        """Test invalid session returns error."""
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute.return_value = mock_result

        result = await process_chat_query(
            db=db,
            user_id=1,
            session_id=999,
            query="test",
        )

        assert "Oturum bulunamadı" in result.answer_text
        assert result.insufficient_context is True

    @pytest.mark.asyncio
    async def test_greeting_shortcut(self):
        """Test greeting returns greeting response without LLM."""
        db = AsyncMock()
        session = ChatSession(id=1, user_id=1, title="Test")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = session
        db.execute.return_value = mock_result

        with patch("app.services.chat_rag_service.get_last_messages", return_value=[]):
            result = await process_chat_query(
                db=db,
                user_id=1,
                session_id=1,
                query="merhaba",
            )

        assert "BIST hisse senedi raporları" in result.answer_text
        assert result.insufficient_context is False

    @pytest.mark.asyncio
    async def test_full_pipeline(self):
        """Test full pipeline execution."""
        db = AsyncMock()
        session = ChatSession(id=1, user_id=1, title="Test")
        mock_session_result = MagicMock()
        mock_session_result.scalar_one_or_none.return_value = session
        db.execute.return_value = mock_session_result
        memory_messages = [
            ChatMessage(id=10, session_id=1, role="user", content="Önceki soru", sources_metadata=[]),
            ChatMessage(id=11, session_id=1, role="assistant", content="Önceki cevap", sources_metadata=[]),
        ]

        with patch("app.services.chat_rag_service.get_last_messages", return_value=memory_messages), \
             patch("app.services.chat_rag_service.analyze_query") as mock_analyze, \
             patch("app.services.chat_rag_service.resolve_symbol") as mock_resolve, \
             patch("app.services.chat_rag_service.run_retrieval") as mock_retrieval, \
             patch("app.services.chat_rag_service.generate_response") as mock_generate:

            from app.schemas.chat import QueryUnderstandingResult, RetrievalAgentResult

            mock_analyze.return_value = QueryUnderstandingResult(
                normalized_query="thyao rapor",
                candidate_symbol="THYAO",
                document_type=DocumentType.FR,
                intent=QueryIntent.SUMMARY,
                confidence=0.9,
            )
            mock_resolve.return_value = "THYAO"
            mock_retrieval.return_value = RetrievalAgentResult(
                chunks=[{"chunk_text": "Test", "score": 0.5, "metadata": {}}],
                sources=[],
                has_sufficient_context=True,
                retrieval_confidence=0.8,
                context_total_chars=100,
            )
            mock_generate.return_value = RAGResponse(
                answer_text="Test response",
                sources=[],
                stock_symbol="THYAO",
                document_type=DocumentType.FR,
                insufficient_context=False,
            )

            result = await process_chat_query(
                db=db,
                user_id=1,
                session_id=1,
                query="thyao yıllık rapor",
            )

        assert result.answer_text == "Test response"
        assert result.stock_symbol == "THYAO"
        assert mock_generate.await_args.kwargs["memory_context"] == format_memory_context(memory_messages)


class TestEnrichRetrievalSources:
    """Tests for enrich_retrieval_sources function."""

    @pytest.mark.asyncio
    async def test_fills_missing_source_url_from_db(self):
        """Test missing source URLs are backfilled from KapReport."""
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.__iter__.return_value = iter([(42, "https://www.kap.org.tr/tr/Bildirim/42")])
        db.execute.return_value = mock_result

        from app.schemas.chat import RetrievalAgentResult, SourceItem

        retrieval = RetrievalAgentResult(
            chunks=[
                {
                    "chunk_text": "Test chunk",
                    "score": 0.4,
                    "metadata": {"kap_report_id": 42, "source_url": ""},
                }
            ],
            sources=[
                SourceItem(
                    kap_report_id=42,
                    stock_symbol="THYAO",
                    report_title="Report",
                    published_at=None,
                    filing_type="FR",
                    source_url="",
                    chunk_preview="Test chunk",
                )
            ],
            has_sufficient_context=True,
            retrieval_confidence=0.8,
            context_total_chars=100,
        )

        enriched = await enrich_retrieval_sources(db, retrieval)

        assert enriched.sources[0].source_url == "https://www.kap.org.tr/tr/Bildirim/42"
        assert enriched.chunks[0]["metadata"]["source_url"] == "https://www.kap.org.tr/tr/Bildirim/42"


class TestCreateChatSession:
    """Tests for create_chat_session function."""

    @pytest.mark.asyncio
    async def test_create_with_title(self):
        """Test create session with title."""
        db = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        result = await create_chat_session(
            db=db,
            user_id=1,
            title="Test Session",
        )

        assert result.user_id == 1
        assert result.title == "Test Session"
        db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_without_title(self):
        """Test create session without title."""
        db = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        result = await create_chat_session(
            db=db,
            user_id=1,
            title=None,
        )

        assert result.user_id == 1
        assert result.title is None


class TestGetUserSessions:
    """Tests for get_user_sessions function."""

    @pytest.mark.asyncio
    async def test_returns_sessions(self):
        """Test returns user sessions."""
        db = AsyncMock()
        sessions = [
            ChatSession(id=1, user_id=1, title="Session 1"),
            ChatSession(id=2, user_id=1, title="Session 2"),
        ]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = sessions
        db.execute.return_value = mock_result

        result = await get_user_sessions(db, user_id=1)

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_empty_result(self):
        """Test empty result when no sessions."""
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db.execute.return_value = mock_result

        result = await get_user_sessions(db, user_id=1)

        assert result == []


class TestSaveMessage:
    """Tests for save_message function."""

    @pytest.mark.asyncio
    async def test_save_user_message(self):
        """Test save user message."""
        db = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        result = await save_message(
            db=db,
            session_id=1,
            role="user",
            content="Test question",
        )

        assert result.session_id == 1
        assert result.role == "user"
        assert result.content == "Test question"
        assert result.sources_metadata == []

    @pytest.mark.asyncio
    async def test_save_assistant_message_with_sources(self):
        """Test save assistant message with sources."""
        db = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        sources = [{"kap_report_id": 1, "stock_symbol": "THYAO"}]

        result = await save_message(
            db=db,
            session_id=1,
            role="assistant",
            content="Test answer",
            sources_metadata=sources,
        )

        assert result.role == "assistant"
        assert result.sources_metadata == sources
