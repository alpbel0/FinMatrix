"""Mock OpenRouter API responses for agent testing.

This module provides HTTP/Service layer mocks for OpenRouter API calls.
Instead of mocking httpx.AsyncClient directly, this mock intercepts at the
service level where the actual HTTP calls are made.

Usage:
    from tests.mocks import MockOpenRouterResponse, MockOpenRouterClient

    response = MockOpenRouterResponse(content='{"query_type":"text_analysis","symbols":["THYAO"]}')
    client = MockOpenRouterClient(responses=[response])
    result = await classify_query("THYAO raporu", http_client=client)
"""

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, MagicMock


@dataclass
class MockOpenRouterResponse:
    """Structured OpenRouter API mock response."""

    content: str
    model: str = "gemma-4-26b-a4b-it:free"
    finish_reason: str = "stop"
    latency_ms: int = 100


class MockOpenRouterClient:
    """Async HTTP client mock for OpenRouter API.

    Tracks all calls made to the mock client for assertion in tests.
    Returns predefined responses in order, cycling through responses list.
    """

    def __init__(
        self,
        responses: list[MockOpenRouterResponse] | MockOpenRouterResponse | None = None,
    ):
        if responses is None:
            self.responses: list[MockOpenRouterResponse] = []
        elif isinstance(responses, list):
            self.responses = responses
        else:
            self.responses = [responses]

        self.response_index: int = 0
        self.calls: list[dict[str, Any]] = []
        self.post = AsyncMock(side_effect=self._mock_post)
        self.aclose = AsyncMock()

    def _mock_post(self, url: str, headers: dict | None = None, json: dict | None = None):
        """Mock POST request to OpenRouter API."""
        self.calls.append({"url": url, "headers": headers, "json": json})

        if self.response_index < len(self.responses):
            response = self.responses[self.response_index]
            self.response_index += 1
        else:
            response = MockOpenRouterResponse(content="{}")

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {"content": response.content},
                    "finish_reason": response.finish_reason,
                }
            ],
            "model": response.model,
            "usage": {"latency_ms": response.latency_ms},
        }
        return mock_response

    def reset(self):
        """Reset call history and response index for reuse."""
        self.calls = []
        self.response_index = 0


def create_mock_openrouter_client(
    responses: list[MockOpenRouterResponse] | MockOpenRouterResponse | None = None,
) -> MockOpenRouterClient:
    """Factory for creating mock OpenRouter client with predefined responses.

    Args:
        responses: Single response, list of responses, or None for empty

    Returns:
        MockOpenRouterClient ready to use as http_client parameter
    """
    return MockOpenRouterClient(responses=responses)


# ---------------------------------------------------------------------------
# Helper factories for common response patterns
# ---------------------------------------------------------------------------


def create_query_classifier_success_response(
    query_type: str,
    symbols: list[str],
    *,
    confidence: float = 0.85,
    reasoning: str = "LLM classified",
    needs_text_analysis: bool = False,
    needs_numerical_analysis: bool = False,
    needs_comparison: bool = False,
    needs_chart: bool = False,
) -> MockOpenRouterResponse:
    """Create a successful query classifier LLM response.

    Args:
        query_type: One of text_analysis, numerical_analysis, comparison, general
        symbols: List of stock symbols
        confidence: Confidence score
        reasoning: Human-readable reasoning
        needs_text_analysis: Whether text analysis is needed
        needs_numerical_analysis: Whether numerical analysis is needed
        needs_comparison: Whether this is a comparison query
        needs_chart: Whether chart output is needed

    Returns:
        MockOpenRouterResponse configured for query classifier
    """
    content = f'{{"query_type":"{query_type}","symbols":{symbols},"confidence":{confidence},"reasoning":"{reasoning}","needs_text_analysis":{str(needs_text_analysis).lower()},"needs_numerical_analysis":{str(needs_numerical_analysis).lower()},"needs_comparison":{str(needs_comparison).lower()},"needs_chart":{str(needs_chart).lower()}}}'
    return MockOpenRouterResponse(content=content)


def create_query_classifier_failure_response() -> MockOpenRouterResponse:
    """Create a fallback response when LLM classification fails.

    Returns:
        MockOpenRouterResponse that will trigger fallback behavior
    """
    return MockOpenRouterResponse(content="invalid json response")


def create_text_analysis_response(
    answer_text: str,
    key_points: list[str] | None = None,
) -> MockOpenRouterResponse:
    """Create a text analysis response (used for response_agent not text_analyst).

    Args:
        answer_text: The main answer text
        key_points: Optional key points

    Returns:
        MockOpenRouterResponse configured for text analysis
    """
    import json

    payload = {"answer_text": answer_text}
    if key_points:
        payload["key_points"] = key_points
    return MockOpenRouterResponse(content=json.dumps(payload))


def create_openrouter_timeout_response() -> MockOpenRouterResponse:
    """Create a response that simulates timeout.

    Returns:
        MockOpenRouterResponse that will cause timeout handling
    """
    return MockOpenRouterResponse(content="")


def create_openrouter_rate_limit_response() -> MockOpenRouterResponse:
    """Create a response that simulates rate limiting.

    Returns:
        MockOpenRouterResponse that will cause rate limit handling
    """
    return MockOpenRouterResponse(content='{"error":{"code":"rate_limit_exceeded"}}')


# ---------------------------------------------------------------------------
# Mock client presets for common test scenarios
# ---------------------------------------------------------------------------


class MockOpenRouterClientPresets:
    """Preset mock clients for common test scenarios."""

    @staticmethod
    def text_analysis_query(symbols: list[str] = None) -> MockOpenRouterClient:
        """Preset for text analysis query classification."""
        if symbols is None:
            symbols = ["THYAO"]
        response = create_query_classifier_success_response(
            query_type="text_analysis",
            symbols=symbols,
            needs_text_analysis=True,
        )
        return create_mock_openrouter_client([response])

    @staticmethod
    def numerical_query(symbols: list[str] = None) -> MockOpenRouterClient:
        """Preset for numerical analysis query classification."""
        if symbols is None:
            symbols = ["THYAO"]
        response = create_query_classifier_success_response(
            query_type="numerical_analysis",
            symbols=symbols,
            needs_numerical_analysis=True,
        )
        return create_mock_openrouter_client([response])

    @staticmethod
    def comparison_query(symbols: list[str] = None) -> MockOpenRouterClient:
        """Preset for comparison query classification."""
        if symbols is None:
            symbols = ["THYAO", "ASELS"]
        response = create_query_classifier_success_response(
            query_type="comparison",
            symbols=symbols,
            needs_text_analysis=True,
            needs_numerical_analysis=True,
            needs_comparison=True,
        )
        return create_mock_openrouter_client([response])

    @staticmethod
    def general_query() -> MockOpenRouterClient:
        """Preset for general query classification."""
        response = create_query_classifier_success_response(
            query_type="general",
            symbols=[],
            confidence=0.5,
        )
        return create_mock_openrouter_client([response])

    @staticmethod
    def fallback_retry() -> MockOpenRouterClient:
        """Preset for fallback model retry scenario."""
        first = MockOpenRouterResponse(content="invalid", model="gemma-4-26b-a4b-it:free")
        second = create_query_classifier_success_response(
            query_type="text_analysis",
            symbols=["THYAO"],
        )
        return create_mock_openrouter_client([first, second])
