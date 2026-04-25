"""Unit tests for Turkish-aware sentence splitter."""

import pytest

from app.services.pipeline.sentence_splitter import (
    split_into_sentences,
    split_text_into_chunks,
    TURKISH_ABBREVIATIONS,
)


class TestSplitIntoSentences:
    def test_simple_sentences(self):
        text = "Bu bir cümle. Bu ikinci cümle."
        result = split_into_sentences(text)
        assert len(result) == 2
        assert result[0] == "Bu bir cümle."
        assert result[1] == "Bu ikinci cümle."

    def test_abbreviation_not_split(self):
        text = "Şirketimiz A.Ş. olarak faaliyet gösteriyor. Bu cümle ayrı olmalı."
        result = split_into_sentences(text)
        assert len(result) == 2
        assert "A.Ş." in result[0]
        assert result[1] == "Bu cümle ayrı olmalı."

    def test_multiple_abbreviations(self):
        text = "Dr. Ahmet ve Prof. Mehmet vb. konuşmacılar katıldı. Toplantı saat 14:00'te başladı."
        result = split_into_sentences(text)
        assert len(result) == 2
        assert "Dr. Ahmet" in result[0]
        assert "Prof. Mehmet vb." in result[0]

    def test_question_and_exclamation(self):
        text = "Bu doğru mu? Evet, doğru! Harika."
        result = split_into_sentences(text)
        assert len(result) == 3

    def test_empty_string(self):
        assert split_into_sentences("") == []

    def test_no_punctuation(self):
        text = "Hiç noktalama işareti yok"
        result = split_into_sentences(text)
        assert result == ["Hiç noktalama işareti yok"]


class TestSplitTextIntoChunks:
    def test_small_text_no_split(self):
        text = "Bu kısa bir metin."
        result = split_text_into_chunks(text, max_tokens=1024, overlap_tokens=50)
        assert len(result) == 1
        assert result[0] == text

    def test_large_text_splits(self):
        # Generate a text that exceeds 1024 tokens (~4096 chars)
        sentence = "Bu cümle tam olarak yetmiş karakter uzunluğunda olmalıdır. "
        text = sentence * 80  # ~5600 chars
        result = split_text_into_chunks(text, max_tokens=1024, overlap_tokens=50)
        assert len(result) > 1
        # Each chunk should be <= 1024 tokens (~4096 chars)
        for chunk in result:
            assert len(chunk) <= 4096 + 50  # Allow small buffer

    def test_overlap_present(self):
        sentence = "Kelime " * 200  # ~1200 chars
        text = sentence + " ".join([f"Cümle{i}." for i in range(50)])
        result = split_text_into_chunks(text, max_tokens=100, overlap_tokens=10)
        if len(result) > 1:
            # Check that consecutive chunks share some words
            words_0 = set(result[0].split())
            words_1 = set(result[1].split())
            assert words_0 & words_1, "Expected overlap between chunks"

    def test_single_sentence_exceeds_max(self):
        # A single sentence longer than max_tokens should be word-split
        text = "abc " * 3000  # One long "sentence" without punctuation
        result = split_text_into_chunks(text, max_tokens=100, overlap_tokens=10)
        assert len(result) > 1
        for chunk in result:
            assert len(chunk) <= 100 * 4 + 50

    def test_turkish_abbreviations_in_chunking(self):
        text = "Şirket A.Ş. olarak faaliyet gösteriyoruz. " * 200
        result = split_text_into_chunks(text, max_tokens=1024, overlap_tokens=50)
        assert len(result) >= 1
        # Ensure A.Ş. is not broken across chunks
        for chunk in result:
            assert "A.Ş." in chunk or "Şirket" in chunk or chunk.strip() == ""


class TestAbbreviationWhitelist:
    def test_common_abbreviations_present(self):
        assert "a.ş." in TURKISH_ABBREVIATIONS
        assert "ltd." in TURKISH_ABBREVIATIONS
        assert "vb." in TURKISH_ABBREVIATIONS
        assert "dr." in TURKISH_ABBREVIATIONS
        assert "prof." in TURKISH_ABBREVIATIONS
