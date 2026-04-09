"""Unit tests for query understanding agent.

Tests:
- Intent classification
- Symbol extraction
- Document type inference
- Confidence scoring
- LLM response parsing
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.schemas.enums import DocumentType, QueryIntent
from app.schemas.chat import QueryUnderstandingResult
from app.services.agents.query_understanding_agent import (
    _map_document_type,
    _map_intent,
    _parse_llm_response,
    _fallback_analysis,
    analyze_query,
    is_greeting,
)


class TestIsGreeting:
    """Tests for is_greeting function."""

    def test_merhaba(self):
        """Test 'merhaba' is recognized as greeting."""
        assert is_greeting("merhaba") is True

    def test_selam(self):
        """Test 'selam' is recognized as greeting."""
        assert is_greeting("selam") is True

    def test_hello(self):
        """Test 'hello' is recognized as greeting."""
        assert is_greeting("hello") is True

    def test_mixed_case(self):
        """Test mixed case greeting."""
        assert is_greeting("MeRhAbA") is True

    def test_greeting_in_sentence(self):
        """Test greeting within sentence."""
        assert is_greeting("merhaba nasılsın") is True

    def test_financial_query_not_greeting(self):
        """Test financial query is not greeting."""
        assert is_greeting("thyao ne kadar") is False

    def test_financial_report_query_not_greeting(self):
        """Test report-style query is not mistaken as greeting."""
        assert is_greeting("THYAO faaliyet raporu ne diyor?") is False

    def test_empty_string(self):
        """Test empty string is not greeting."""
        assert is_greeting("") is False


class TestParseLlmResponse:
    """Tests for _parse_llm_response function."""

    def test_valid_json(self):
        """Test valid JSON parsing."""
        response = '{"intent": "SUMMARY", "confidence": 0.8}'
        result = _parse_llm_response(response)
        assert result["intent"] == "SUMMARY"
        assert result["confidence"] == 0.8

    def test_json_in_markdown_block(self):
        """Test JSON extraction from markdown code block."""
        response = '```json\n{"intent": "RISK"}\n```'
        result = _parse_llm_response(response)
        assert result["intent"] == "RISK"

    def test_json_with_surrounding_text(self):
        """Test JSON extraction from text with surrounding content."""
        response = 'Here is the result: {"intent": "METRIC"} end'
        result = _parse_llm_response(response)
        assert result["intent"] == "METRIC"

    def test_invalid_json_returns_empty(self):
        """Test invalid JSON returns empty dict."""
        response = "not valid json at all"
        result = _parse_llm_response(response)
        assert result == {}

    def test_empty_response(self):
        """Test empty response returns empty dict."""
        result = _parse_llm_response("")
        assert result == {}


class TestMapIntent:
    """Tests for _map_intent function."""

    def test_summary(self):
        """Test SUMMARY mapping."""
        assert _map_intent("SUMMARY") == QueryIntent.SUMMARY

    def test_risk(self):
        """Test RISK mapping."""
        assert _map_intent("RISK") == QueryIntent.RISK

    def test_opportunity(self):
        """Test OPPORTUNITY mapping."""
        assert _map_intent("OPPORTUNITY") == QueryIntent.OPPORTUNITY

    def test_metric(self):
        """Test METRIC mapping."""
        assert _map_intent("METRIC") == QueryIntent.METRIC

    def test_generic(self):
        """Test GENERIC mapping."""
        assert _map_intent("GENERIC") == QueryIntent.GENERIC

    def test_lowercase(self):
        """Test lowercase input."""
        assert _map_intent("summary") == QueryIntent.SUMMARY

    def test_unknown_returns_generic(self):
        """Test unknown intent returns GENERIC."""
        assert _map_intent("UNKNOWN") == QueryIntent.GENERIC


class TestMapDocumentType:
    """Tests for _map_document_type function."""

    def test_fr(self):
        """Test FR mapping."""
        assert _map_document_type("FR") == DocumentType.FR

    def test_far(self):
        """Test FAR mapping."""
        assert _map_document_type("FAR") == DocumentType.FAR

    def test_any(self):
        """Test ANY mapping."""
        assert _map_document_type("ANY") == DocumentType.ANY

    def test_none_returns_any(self):
        """Test None returns ANY."""
        assert _map_document_type(None) == DocumentType.ANY

    def test_unknown_returns_any(self):
        """Test unknown type returns ANY."""
        assert _map_document_type("UNKNOWN") == DocumentType.ANY


class TestAnalyzeQuery:
    """Tests for analyze_query function."""

    @pytest.mark.asyncio
    async def test_successful_analysis(self):
        """Test successful query analysis."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "normalized_query": "thyao yıllık rapor",
                        "candidate_symbol": "THYAO",
                        "document_type": "FR",
                        "intent": "SUMMARY",
                        "confidence": 0.9
                    })
                }
            }]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        with patch("app.services.agents.query_understanding_agent.load_prompt") as mock_load:
            mock_load.return_value = MagicMock(
                model="test-model",
                system_prompt="test",
                user_prompt_template="{query}",
                temperature=0.3,
                max_tokens=512,
                format_user_prompt=lambda **kw: "test prompt"
            )

            result = await analyze_query("thyao yıllık rapor", mock_client)

        assert result.intent == QueryIntent.SUMMARY
        assert result.candidate_symbol == "THYAO"
        assert result.document_type == DocumentType.FR
        assert result.confidence == 0.9

    @pytest.mark.asyncio
    async def test_llm_error_returns_default(self):
        """Test LLM error returns heuristic fallback result."""
        mock_client = AsyncMock()
        mock_client.post.side_effect = Exception("API error")

        with patch("app.services.agents.query_understanding_agent.load_prompt") as mock_load:
            mock_load.return_value = MagicMock(
                model="test-model",
                system_prompt="test",
                user_prompt_template="{query}",
                temperature=0.3,
                max_tokens=512,
                format_user_prompt=lambda **kw: "test prompt"
            )

            result = await analyze_query("test query", mock_client)

        assert result.intent == QueryIntent.SUMMARY
        assert result.document_type == DocumentType.ANY
        assert result.confidence == 0.3

    @pytest.mark.asyncio
    async def test_llm_error_financial_query_uses_heuristics(self):
        """Test fallback keeps financial queries out of greeting path."""
        mock_client = AsyncMock()
        mock_client.post.side_effect = Exception("API error")

        with patch("app.services.agents.query_understanding_agent.load_prompt") as mock_load:
            mock_load.return_value = MagicMock(
                model="test-model",
                system_prompt="test",
                user_prompt_template="{query}",
                temperature=0.3,
                max_tokens=512,
                format_user_prompt=lambda **kw: "test prompt"
            )

            result = await analyze_query("THYAO faaliyet raporu ne diyor?", mock_client)

        assert result.intent == QueryIntent.SUMMARY
        assert result.document_type == DocumentType.FAR
        assert result.candidate_symbol == "THYAO"


class TestFallbackAnalysis:
    """Tests for heuristic fallback logic."""

    def test_report_query_maps_to_summary_and_far(self):
        result = _fallback_analysis("THYAO faaliyet raporu ne diyor?")
        assert result.intent == QueryIntent.SUMMARY
        assert result.document_type == DocumentType.FAR
        assert result.candidate_symbol == "THYAO"
