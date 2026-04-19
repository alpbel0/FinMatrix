"""Unit tests for chat RAG service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.chat import ChatMessage, ChatSession
from app.schemas.chat import RAGResponse
from app.schemas.enums import DocumentType
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
    def test_empty_messages(self):
        assert format_memory_context([]) == ""

    def test_single_user_message(self):
        msg = ChatMessage(id=1, session_id=1, role="user", content="Test question", sources_metadata=[])
        assert "Kullan" in format_memory_context([msg])

    def test_single_assistant_message(self):
        msg = ChatMessage(id=1, session_id=1, role="assistant", content="Test answer", sources_metadata=[])
        assert "Asistan: Test answer" in format_memory_context([msg])

    def test_multiple_messages(self):
        messages = [
            ChatMessage(id=1, session_id=1, role="user", content="Q1", sources_metadata=[]),
            ChatMessage(id=2, session_id=1, role="assistant", content="A1", sources_metadata=[]),
            ChatMessage(id=3, session_id=1, role="user", content="Q2", sources_metadata=[]),
        ]
        result = format_memory_context(messages)
        assert "Q1" in result
        assert "A1" in result
        assert "Q2" in result

    def test_long_message_truncation(self):
        msg = ChatMessage(id=1, session_id=1, role="user", content="x" * 500, sources_metadata=[])
        result = format_memory_context([msg])
        assert len(result.split(": ")[1]) == 200


class TestGetLastMessages:
    @pytest.mark.asyncio
    async def test_empty_result(self):
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db.execute.return_value = mock_result
        assert await get_last_messages(db, session_id=1, limit=5) == []

    @pytest.mark.asyncio
    async def test_returns_messages(self):
        db = AsyncMock()
        messages = [ChatMessage(id=1, session_id=1, role="user", content="Test", sources_metadata=[])]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = messages
        db.execute.return_value = mock_result
        result = await get_last_messages(db, session_id=1, limit=5)
        assert len(result) == 1


class TestProcessChatQuery:
    @pytest.mark.asyncio
    async def test_invalid_session(self):
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute.return_value = mock_result

        result = await process_chat_query(db=db, user_id=1, session_id=999, query="test")

        assert "Oturum bulunamad" in result.answer_text
        assert result.insufficient_context is True

    @pytest.mark.asyncio
    async def test_greeting_shortcut(self):
        db = AsyncMock()
        session = ChatSession(id=1, user_id=1, title="Test")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = session
        db.execute.return_value = mock_result

        result = await process_chat_query(db=db, user_id=1, session_id=1, query="merhaba")

        assert "BIST hisse senedi rapor" in result.answer_text
        assert result.insufficient_context is False

    @pytest.mark.asyncio
    async def test_full_pipeline(self):
        db = AsyncMock()
        session = ChatSession(id=1, user_id=1, title="Test")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = session
        db.execute.return_value = mock_result

        mock_pipeline = MagicMock()
        mock_pipeline.response = RAGResponse(
            answer_text="Test response",
            sources=[],
            stock_symbol="THYAO",
            document_type=DocumentType.FR,
            insufficient_context=False,
        )

        with patch(
            "app.services.agents.orchestrator.run_orchestrated_pipeline",
            AsyncMock(return_value=mock_pipeline),
        ) as mock_orchestrated:
            result = await process_chat_query(
                db=db,
                user_id=1,
                session_id=1,
                query="thyao yillik rapor",
            )

        assert result.answer_text == "Test response"
        assert result.stock_symbol == "THYAO"
        mock_orchestrated.assert_awaited_once()


class TestEnrichRetrievalSources:
    @pytest.mark.asyncio
    async def test_fills_missing_source_url_from_db(self):
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.__iter__.return_value = iter([(42, "https://www.kap.org.tr/tr/Bildirim/42")])
        db.execute.return_value = mock_result

        from app.schemas.chat import RetrievalAgentResult, SourceItem

        retrieval = RetrievalAgentResult(
            chunks=[{"chunk_text": "Test chunk", "score": 0.4, "metadata": {"kap_report_id": 42, "source_url": ""}}],
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

        assert enriched.sources[0].source_url.endswith("/42")
        assert enriched.chunks[0]["metadata"]["source_url"].endswith("/42")


class TestCreateChatSession:
    @pytest.mark.asyncio
    async def test_create_with_title(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        result = await create_chat_session(db=db, user_id=1, title="Test Session")

        assert result.user_id == 1
        assert result.title == "Test Session"
        db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_without_title(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        result = await create_chat_session(db=db, user_id=1, title=None)

        assert result.user_id == 1
        assert result.title is None


class TestGetUserSessions:
    @pytest.mark.asyncio
    async def test_returns_sessions(self):
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
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db.execute.return_value = mock_result
        assert await get_user_sessions(db, user_id=1) == []


class TestSaveMessage:
    @pytest.mark.asyncio
    async def test_save_user_message(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        result = await save_message(db=db, session_id=1, role="user", content="Test question")

        assert result.session_id == 1
        assert result.role == "user"
        assert result.content == "Test question"
        assert result.sources_metadata == []

    @pytest.mark.asyncio
    async def test_save_assistant_message_with_sources(self):
        db = AsyncMock()
        db.add = MagicMock()
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
