"""Unit tests for CrewAI-ready query classifier."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.enums import QueryType
from app.services.agents.query_classifier import (
    _extract_symbol_candidates,
    classify_query,
    classify_query_heuristic,
)


class TestExtractSymbolCandidates:
    """Tests for lightweight symbol extraction."""

    def test_extracts_alias_and_symbol(self):
        symbols = _extract_symbol_candidates("thy ile ASELS karşılaştır")
        assert "THYAO" in symbols
        assert "ASELS" in symbols

    def test_greeting_not_preferred_over_symbol(self):
        symbols = _extract_symbol_candidates("Selam THYAO raporunu yorumla")
        assert symbols[0] == "THYAO"


class TestClassifyQueryHeuristic:
    """Tests for deterministic classifier path."""

    def test_text_analysis_report_query(self):
        result = classify_query_heuristic("THYAO faaliyet raporu ne diyor?")
        assert result.query_type == QueryType.TEXT_ANALYSIS
        assert result.needs_text_analysis is True
        assert result.needs_numerical_analysis is False
        assert "THYAO" in result.symbols

    def test_numerical_metric_query(self):
        result = classify_query_heuristic("THYAO net kar nasıl?")
        assert result.query_type == QueryType.NUMERICAL_ANALYSIS
        assert result.needs_numerical_analysis is True

    def test_comparison_query(self):
        result = classify_query_heuristic("THYAO ile ASELS net kar karşılaştır")
        assert result.query_type == QueryType.COMPARISON
        assert result.needs_comparison is True
        assert result.needs_numerical_analysis is True
        assert "THYAO" in result.symbols
        assert "ASELS" in result.symbols

    def test_greeting_query(self):
        result = classify_query_heuristic("merhaba")
        assert result.query_type == QueryType.GENERAL
        assert result.confidence >= 0.85

    def test_ambiguous_query_has_low_confidence(self):
        result = classify_query_heuristic("thy tarafı nasıl")
        assert result.confidence < 0.85


class TestClassifyQuery:
    """Tests for public classifier function."""

    @pytest.mark.asyncio
    async def test_obvious_query_does_not_call_llm(self):
        mock_client = AsyncMock()
        result = await classify_query("THYAO faaliyet raporu ne diyor?", http_client=mock_client)
        assert result.query_type == QueryType.TEXT_ANALYSIS
        mock_client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_ambiguous_query_uses_llm_payload(self):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": '{"query_type":"text_analysis","symbols":["THYAO"],"needs_text_analysis":true,"confidence":0.8,"reasoning":"mentions THY"}'
                    }
                }
            ]
        }
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        with patch("app.services.agents.query_classifier.load_prompt") as mock_load:
            mock_load.return_value = MagicMock(
                system_prompt="system",
                temperature=0.1,
                max_tokens=700,
                format_user_prompt=lambda **kwargs: kwargs["query"],
            )
            result = await classify_query("thy tarafı nasıl", http_client=mock_client)

        assert result.query_type == QueryType.TEXT_ANALYSIS
        assert result.symbols == ["THYAO"]
        assert result.needs_text_analysis is True

    @pytest.mark.asyncio
    async def test_llm_failure_returns_safe_fallback(self):
        mock_client = AsyncMock()
        mock_client.post.side_effect = RuntimeError("boom")

        with patch("app.services.agents.query_classifier.load_prompt") as mock_load:
            mock_load.return_value = MagicMock(
                system_prompt="system",
                temperature=0.1,
                max_tokens=700,
                format_user_prompt=lambda **kwargs: kwargs["query"],
            )
            result = await classify_query("thy tarafı nasıl", http_client=mock_client)

        assert result.query_type == QueryType.GENERAL
        assert result.confidence == 0.4

    @pytest.mark.asyncio
    async def test_llm_classification_text_analysis(self):
        """Test LLM path for text analysis query."""
        from tests.mocks import MockOpenRouterClient, create_query_classifier_success_response

        response = create_query_classifier_success_response(
            query_type="text_analysis",
            symbols=["THYAO"],
            needs_text_analysis=True,
        )
        mock_client = MockOpenRouterClient(responses=[response])

        with patch("app.services.agents.query_classifier.load_prompt") as mock_load:
            mock_load.return_value = MagicMock(
                system_prompt="system",
                temperature=0.1,
                max_tokens=700,
                format_user_prompt=lambda **kwargs: kwargs["query"],
            )
            result = await classify_query("THYAO faaliyet raporu ne diyor?", http_client=mock_client)

        assert result.query_type == QueryType.TEXT_ANALYSIS
        assert result.symbols == ["THYAO"]
        assert result.needs_text_analysis is True

    @pytest.mark.asyncio
    async def test_llm_classification_numerical(self):
        """Test LLM path for numerical analysis query."""
        from tests.mocks import MockOpenRouterClient, create_query_classifier_success_response

        response = create_query_classifier_success_response(
            query_type="numerical_analysis",
            symbols=["GARAN"],
            needs_numerical_analysis=True,
        )
        mock_client = MockOpenRouterClient(responses=[response])

        with patch("app.services.agents.query_classifier.load_prompt") as mock_load:
            mock_load.return_value = MagicMock(
                system_prompt="system",
                temperature=0.1,
                max_tokens=700,
                format_user_prompt=lambda **kwargs: kwargs["query"],
            )
            result = await classify_query("GARAN net kar ne?", http_client=mock_client)

        assert result.query_type == QueryType.NUMERICAL_ANALYSIS
        assert "GARAN" in result.symbols

    @pytest.mark.asyncio
    async def test_llm_classification_comparison(self):
        """Test LLM path for comparison query."""
        from tests.mocks import MockOpenRouterClient, create_query_classifier_success_response

        response = create_query_classifier_success_response(
            query_type="comparison",
            symbols=["THYAO", "ASELS"],
            needs_text_analysis=True,
            needs_numerical_analysis=True,
            needs_comparison=True,
        )
        mock_client = MockOpenRouterClient(responses=[response])

        with patch("app.services.agents.query_classifier.load_prompt") as mock_load:
            mock_load.return_value = MagicMock(
                system_prompt="system",
                temperature=0.1,
                max_tokens=700,
                format_user_prompt=lambda **kwargs: kwargs["query"],
            )
            result = await classify_query("THYAO ile ASELS karsilastir", http_client=mock_client)

        assert result.query_type == QueryType.COMPARISON
        assert "THYAO" in result.symbols
        assert "ASELS" in result.symbols
        assert result.needs_comparison is True

    @pytest.mark.asyncio
    async def test_llm_retry_with_fallback_model(self):
        """Test fallback model retry behavior."""
        from tests.mocks import (
            MockOpenRouterClient,
            MockOpenRouterResponse,
            create_query_classifier_success_response,
        )

        first_response = MockOpenRouterResponse(content="not valid json {{{")
        second_response = create_query_classifier_success_response(
            query_type="text_analysis",
            symbols=["THYAO"],
            needs_text_analysis=True,
        )
        mock_client = MockOpenRouterClient(responses=[first_response, second_response])

        with patch("app.services.agents.query_classifier.load_prompt") as mock_load:
            mock_load.return_value = MagicMock(
                system_prompt="system",
                temperature=0.1,
                max_tokens=700,
                format_user_prompt=lambda **kwargs: kwargs["query"],
            )
            # Use ambiguous query that triggers LLM path (confidence < 0.85)
            result = await classify_query("thy tarafı nasıl", http_client=mock_client)

        assert len(mock_client.calls) == 2

    @pytest.mark.asyncio
    async def test_llm_invalid_json_handling(self):
        """Test graceful handling of invalid JSON from LLM."""
        from tests.mocks import MockOpenRouterClient, MockOpenRouterResponse

        mock_client = MockOpenRouterClient(
            responses=[MockOpenRouterResponse(content="not valid json {{{")]
        )

        with patch("app.services.agents.query_classifier.load_prompt") as mock_load:
            mock_load.return_value = MagicMock(
                system_prompt="system",
                temperature=0.1,
                max_tokens=700,
                format_user_prompt=lambda **kwargs: kwargs["query"],
            )
            result = await classify_query("thy tarafi", http_client=mock_client)

        assert result.query_type == QueryType.GENERAL
        assert result.confidence == 0.4

    @pytest.mark.asyncio
    async def test_classify_query_with_http_timeout(self):
        """Test timeout handling in LLM path."""
        import httpx

        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.TimeoutException("timeout")

        with patch("app.services.agents.query_classifier.load_prompt") as mock_load:
            mock_load.return_value = MagicMock(
                system_prompt="system",
                temperature=0.1,
                max_tokens=700,
                format_user_prompt=lambda **kwargs: kwargs["query"],
            )
            result = await classify_query("thy tarafi", http_client=mock_client)

        assert result.query_type == QueryType.GENERAL
        assert result.confidence == 0.4

    @pytest.mark.asyncio
    async def test_classify_query_confidence_threshold(self):
        """Test confidence threshold - queries above 0.85 skip LLM."""
        mock_client = AsyncMock()

        result = await classify_query("THYAO net kar nasil?", http_client=mock_client)

        assert result.confidence >= 0.85
        mock_client.post.assert_not_called()
