"""Unit tests for triage_service module.

Covers deterministic triage rules, LLM response parsing, cache logic,
and the full filter_elements pipeline with mocked DB + HTTP.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.pipeline.document_parser import ParsedElement
from app.services.pipeline.triage_service import (
    TriageDecision,
    TriageItem,
    TriageResult,
    _batch_llm_triage,
    _build_triage_prompt,
    _deterministic_triage,
    _make_text_preview,
    _matches_any,
    _normalize_section_path,
    _parse_llm_response,
    filter_elements,
)


# ---------------------------------------------------------------------------
# Deterministic triage tests
# ---------------------------------------------------------------------------


class TestBlacklist:
    def test_bagimsiz_denetci_discarded(self):
        el = ParsedElement(
            element_type="paragraph",
            text="Some text",
            markdown="Some text",
            page_start=1,
            page_end=1,
            section_path="Bağımsız Denetçi Görüşü",
        )
        result = _deterministic_triage(el)
        assert result.decision == TriageDecision.DISCARD
        assert result.reason == "blacklist_match"

    def test_kapak_sayfasi_discarded(self):
        el = ParsedElement(
            element_type="paragraph",
            text="Cover",
            markdown="Cover",
            page_start=1,
            page_end=1,
            section_path="Kapak Sayfası",
        )
        result = _deterministic_triage(el)
        assert result.decision == TriageDecision.DISCARD

    def test_toc_discarded(self):
        el = ParsedElement(
            element_type="paragraph",
            text="Contents",
            markdown="Contents",
            page_start=1,
            page_end=1,
            section_path="İçindekiler",
        )
        result = _deterministic_triage(el)
        assert result.decision == TriageDecision.DISCARD


class TestWhitelist:
    def test_bilanco_kept(self):
        el = ParsedElement(
            element_type="table",
            text="Assets ...",
            markdown="Assets ...",
            page_start=1,
            page_end=1,
            section_path="Bilanço",
        )
        result = _deterministic_triage(el)
        assert result.decision == TriageDecision.KEEP
        assert result.reason == "whitelist_match"

    def test_yonetim_kurulu_raporu_kept(self):
        el = ParsedElement(
            element_type="paragraph",
            text="Yönetim Kurulu raporu içeriği",
            markdown="...",
            page_start=1,
            page_end=1,
            section_path="Yönetim Kurulu Raporu",
        )
        result = _deterministic_triage(el)
        assert result.decision == TriageDecision.KEEP
        assert result.reason == "whitelist_match"

    def test_risk_yonetimi_kept(self):
        el = ParsedElement(
            element_type="paragraph",
            text="Risk yönetimi süreçleri",
            markdown="...",
            page_start=1,
            page_end=1,
            section_path="Risk Yönetimi",
        )
        result = _deterministic_triage(el)
        assert result.decision == TriageDecision.KEEP


class TestGreylistQuickDiscard:
    def test_too_short_no_alpha_discarded(self):
        el = ParsedElement(
            element_type="paragraph",
            text="14",
            markdown="14",
            page_start=1,
            page_end=1,
            section_path="",
        )
        result = _deterministic_triage(el)
        assert result.decision == TriageDecision.DISCARD
        assert result.reason == "greylist_too_short_no_alpha"

    def test_dash_only_discarded(self):
        el = ParsedElement(
            element_type="paragraph",
            text="- -",
            markdown="- -",
            page_start=1,
            page_end=1,
            section_path="",
        )
        result = _deterministic_triage(el)
        assert result.decision == TriageDecision.DISCARD

    def test_short_but_alpha_kept_for_llm(self):
        el = ParsedElement(
            element_type="paragraph",
            text="AB",
            markdown="AB",
            page_start=1,
            page_end=1,
            section_path="Bilinmeyen Bölüm",
        )
        result = _deterministic_triage(el)
        # Not blacklisted, not whitelisted, but has alpha -> greylist
        assert result.decision == TriageDecision.REVIEW
        assert result.reason == "greylist"


class TestUnknownSection:
    def test_unknown_non_empty_greylist(self):
        el = ParsedElement(
            element_type="paragraph",
            text="Some random text here.",
            markdown="Some random text here.",
            page_start=1,
            page_end=1,
            section_path="Rastgele Bir Başlık",
        )
        result = _deterministic_triage(el)
        assert result.decision == TriageDecision.REVIEW
        assert result.reason == "greylist"


# ---------------------------------------------------------------------------
# Helper tests
# ---------------------------------------------------------------------------


class TestNormalizeSectionPath:
    def test_lowercase_and_trim(self):
        assert _normalize_section_path("  Bilanço ") == "bilanço"

    def test_empty(self):
        assert _normalize_section_path("") == ""

    def test_none(self):
        assert _normalize_section_path(None) == ""


class TestMatchesAny:
    def test_no_patterns(self):
        import re
        assert _matches_any("text", []) is False

    def test_match_found(self):
        import re
        patterns = [re.compile(r"bilanço", re.IGNORECASE)]
        assert _matches_any("Bilanço Tablosu", patterns) is True

    def test_no_match(self):
        import re
        patterns = [re.compile(r"bilanço", re.IGNORECASE)]
        assert _matches_any("Gelir Tablosu", patterns) is False


class TestMakeTextPreview:
    def test_short_text_unchanged(self):
        text = "Kısa bir metin."
        assert _make_text_preview(text) == text

    def test_long_text_truncated(self):
        text = "A. " * 500
        preview = _make_text_preview(text)
        assert len(preview) <= 400
        assert preview.endswith("...") or preview.endswith(".")


# ---------------------------------------------------------------------------
# LLM response parsing tests
# ---------------------------------------------------------------------------


class TestParseLLMResponse:
    def test_basic_keep(self):
        text = json.dumps([{"is_valuable": True, "suggested_section": None}])
        results = _parse_llm_response(text, 1)
        assert results[0].decision == TriageDecision.KEEP

    def test_synthetic(self):
        text = json.dumps([{"is_valuable": True, "suggested_section": "Finansal Analiz"}])
        results = _parse_llm_response(text, 1)
        assert results[0].decision == TriageDecision.SYNTHETIC
        assert results[0].suggested_section == "Finansal Analiz"

    def test_discard(self):
        text = json.dumps([{"is_valuable": False, "suggested_section": None}])
        results = _parse_llm_response(text, 1)
        assert results[0].decision == TriageDecision.DISCARD

    def test_markdown_wrapped(self):
        text = "```json\n" + json.dumps([{"is_valuable": True}]) + "\n```"
        results = _parse_llm_response(text, 1)
        assert results[0].decision == TriageDecision.KEEP

    def test_undercount_fallback(self):
        text = json.dumps([{"is_valuable": True}])
        results = _parse_llm_response(text, 3)
        assert len(results) == 3
        assert results[0].decision == TriageDecision.KEEP
        assert results[1].decision == TriageDecision.KEEP
        assert results[2].reason == "llm_undercount_fallback"

    def test_invalid_json_fallback(self):
        results = _parse_llm_response("not json", 2)
        assert len(results) == 2
        assert all(r.decision == TriageDecision.KEEP for r in results)
        assert all(r.reason == "parse_error_fallback" for r in results)


# ---------------------------------------------------------------------------
# Prompt building tests
# ---------------------------------------------------------------------------


class TestBuildTriagePrompt:
    def test_includes_element_type(self):
        items = [
            TriageItem(
                element=MagicMock(),
                section_path="Bilanço",
                text_preview="Assets 1000",
                element_type="table",
            )
        ]
        prompt = _build_triage_prompt(items, "THYAO", 2025)
        assert "Type: table" in prompt
        assert "Section: Bilanço" in prompt
        assert "THYAO" in prompt
        assert "2025" in prompt

    def test_none_section_path(self):
        items = [
            TriageItem(
                element=MagicMock(),
                section_path=None,
                text_preview="Some text",
                element_type="paragraph",
            )
        ]
        prompt = _build_triage_prompt(items, "GARAN", 2024)
        assert "Section: (None)" in prompt
        assert "Type: paragraph" in prompt

    def test_multiple_items(self):
        items = [
            TriageItem(
                element=MagicMock(),
                section_path="A",
                text_preview="Text A",
                element_type="heading",
            ),
            TriageItem(
                element=MagicMock(),
                section_path="B",
                text_preview="Text B",
                element_type="paragraph",
            ),
        ]
        prompt = _build_triage_prompt(items, "ASELS", 2025)
        assert "1. Section: A" in prompt
        assert "2. Section: B" in prompt
        assert "Type: heading" in prompt
        assert "Type: paragraph" in prompt


# ---------------------------------------------------------------------------
# Integration-style tests with mocked DB and HTTP
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db():
    """Return a mock AsyncSession."""
    db = AsyncMock()
    db.execute = AsyncMock()
    return db


@pytest.fixture
def mock_scalars():
    """Helper to mock scalar_one_or_none / all returns."""
    def _make_scalars(return_value):
        mock = MagicMock()
        mock.scalar_one_or_none.return_value = return_value
        mock.all.return_value = return_value if isinstance(return_value, list) else []
        return mock
    return _make_scalars


class TestFilterElements:
    async def test_all_blacklisted_discarded(self, mock_db):
        elements = [
            ParsedElement(
                element_type="paragraph",
                text="text1",
                markdown="text1",
                page_start=1,
                page_end=1,
                section_path="Bağımsız Denetçi Görüşü",
            ),
            ParsedElement(
                element_type="paragraph",
                text="text2",
                markdown="text2",
                page_start=1,
                page_end=1,
                section_path="Kapak Sayfası",
            ),
        ]
        result = await filter_elements(elements, mock_db)
        assert len(result) == 0

    async def test_whitelist_kept_no_llm(self, mock_db):
        elements = [
            ParsedElement(
                element_type="table",
                text="Assets",
                markdown="Assets",
                page_start=1,
                page_end=1,
                section_path="Bilanço",
            )
        ]
        result = await filter_elements(elements, mock_db)
        assert len(result) == 1
        assert result[0][1].decision == TriageDecision.KEEP

    @patch("app.services.pipeline.triage_service._resolve_via_cache_and_llm", new_callable=AsyncMock)
    async def test_greylist_goes_to_llm(self, mock_resolve, mock_db):
        elements = [
            ParsedElement(
                element_type="paragraph",
                text="This is a valuable paragraph about financial performance.",
                markdown="...",
                page_start=1,
                page_end=1,
                section_path="Unknown Section",
            )
        ]
        mock_resolve.return_value = [
            TriageResult(decision=TriageDecision.KEEP, reason="llm_keep")
        ]
        result = await filter_elements(elements, mock_db)
        assert len(result) == 1
        assert result[0][1].reason == "llm_keep"
        mock_resolve.assert_awaited_once()

    @patch("app.services.pipeline.triage_service._resolve_via_cache_and_llm", new_callable=AsyncMock)
    async def test_none_section_path_synthetic(self, mock_resolve, mock_db):
        elements = [
            ParsedElement(
                element_type="paragraph",
                text="Net kar 5 milyar TL olarak gerçekleşmiştir.",
                markdown="...",
                page_start=1,
                page_end=1,
                section_path="",
            )
        ]
        mock_resolve.return_value = [
            TriageResult(
                decision=TriageDecision.SYNTHETIC,
                suggested_section="Finansal Özet",
                reason="llm_synthetic",
            )
        ]
        result = await filter_elements(elements, mock_db)
        assert len(result) == 1
        assert result[0][0].section_path == "Finansal Özet"
        assert result[0][0].is_synthetic is True

    @patch("app.services.pipeline.triage_service._resolve_via_cache_and_llm", new_callable=AsyncMock)
    async def test_greylist_discarded(self, mock_resolve, mock_db):
        elements = [
            ParsedElement(
                element_type="paragraph",
                text="Random unknown text.",
                markdown="...",
                page_start=1,
                page_end=1,
                section_path="Some Weird Section",
            )
        ]
        mock_resolve.return_value = [
            TriageResult(decision=TriageDecision.DISCARD, reason="llm_discard")
        ]
        result = await filter_elements(elements, mock_db)
        assert len(result) == 0


class TestBatchLLMTriage:
    @patch("app.services.pipeline.triage_service._single_llm_call", new_callable=AsyncMock)
    async def test_batches_items(self, mock_single):
        def _side_effect(batch, **kwargs):
            return [
                TriageResult(decision=TriageDecision.KEEP, reason="llm_keep")
                for _ in batch
            ]

        mock_single.side_effect = _side_effect
        items = [
            TriageItem(
                element=MagicMock(),
                section_path=f"Section {i}",
                text_preview=f"Text {i}",
                element_type="paragraph",
            )
            for i in range(30)
        ]
        results = await _batch_llm_triage(items, stock_symbol="THYAO", report_year=2025)
        assert len(results) == 30
        # Should be called twice (25 + 5)
        assert mock_single.call_count == 2

    @patch("app.services.pipeline.triage_service.get_settings")
    async def test_no_api_key_fallback(self, mock_get_settings):
        settings = MagicMock()
        settings.openrouter_api_key = ""
        mock_get_settings.return_value = settings

        items = [
            TriageItem(
                element=MagicMock(),
                section_path="A",
                text_preview="B",
                element_type="paragraph",
            )
        ]
        results = await _batch_llm_triage(items, stock_symbol="THYAO", report_year=2025)
        assert results[0].decision == TriageDecision.KEEP
        assert results[0].reason == "no_api_key_fallback"
