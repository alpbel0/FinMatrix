"""Turkish-aware sentence splitting utilities.

Handles common Turkish abbreviations (A.Ş., vb., vs., Dr., etc.)
so they are not mistaken for sentence boundaries.
"""

from __future__ import annotations

import re

# Whitelist of Turkish abbreviations that end with a period but are NOT sentence boundaries.
# All entries should be lowercased for case-insensitive matching.
TURKISH_ABBREVIATIONS = frozenset(
    {
        "a.ş.",
        "a.s.",
        "ltd.",
        "şti.",
        "sti.",
        "no.",
        "vb.",
        "vs.",
        "dr.",
        "prof.",
        "doç.",
        "doc.",
        "yrd.",
        "bknz.",
        "bkz.",
        "s.",
        "sf.",
        "say.",
        "yıl.",
        "yil.",
        "kr.",
        "tl.",
        "usd",
        "eur",
        "gbp",
        "örn.",
        "orn.",
        "yakl.",
        "yak.",
        "yaklaşık",
        "yaklasik",
        "mn.",
        "milyon",
        "milyar",
        "bin",
        "ad.",
        "adet",
        "kiş.",
        "kisi.",
        "kişi",
        "kisi",
        "etc.",
        "inc.",
        "co.",
        "corp.",
        "ltd.",
    }
)

# Sentence boundary punctuation in Turkish
_SENTENCE_END_RE = re.compile(r"[.!?]+\s+")


def _is_abbreviation_at(text: str, end_pos: int) -> bool:
    """Check if the token ending at *end_pos* is an abbreviation."""
    # Walk backwards to find the start of the token (space or start of string)
    start = end_pos - 1
    while start >= 0 and not text[start].isspace():
        start -= 1
    token = text[start + 1 : end_pos + 1].strip().lower().rstrip(".!?")
    # Re-add the trailing period for exact abbreviation match
    token_with_period = token + "."
    return token_with_period in TURKISH_ABBREVIATIONS


def split_into_sentences(text: str) -> list[str]:
    """Split *text* into sentences, respecting Turkish abbreviations.

    Args:
        text: Input text (may contain multiple sentences).

    Returns:
        List of sentence strings.
    """
    if not text:
        return []

    sentences: list[str] = []
    current_start = 0

    for match in _SENTENCE_END_RE.finditer(text):
        # The punctuation itself ends at match.end() - 1 (the space after it is match.end())
        punct_end = match.end() - 1
        # If the token before the punctuation is an abbreviation, skip
        if _is_abbreviation_at(text, punct_end - 1):
            continue
        sentence = text[current_start : match.end()].strip()
        if sentence:
            sentences.append(sentence)
        current_start = match.end()

    # Trailing text after last sentence boundary
    trailing = text[current_start:].strip()
    if trailing:
        sentences.append(trailing)

    return sentences


def split_text_into_chunks(
    text: str,
    max_tokens: int = 1024,
    overlap_tokens: int = 50,
    chars_per_token: int = 4,
) -> list[str]:
    """Split *text* into chunks that do not exceed *max_tokens*.

    Strategy:
      1. Try to split at sentence boundaries (Turkish-aware).
      2. If a single sentence still exceeds the limit, split at word boundaries
         and append ``" [...]"`` to indicate truncation.

    Args:
        text: The text to split.
        max_tokens: Maximum tokens per chunk.
        overlap_tokens: Tokens to overlap between consecutive chunks.
        chars_per_token: Heuristic for Turkish text (~4 chars/token).

    Returns:
        List of chunk strings.
    """
    max_chars = max_tokens * chars_per_token
    overlap_chars = overlap_tokens * chars_per_token

    sentences = split_into_sentences(text)
    if not sentences:
        return [text] if text else []

    chunks: list[str] = []
    current_chunk_sentences: list[str] = []
    current_chars = 0

    def flush() -> str:
        nonlocal current_chunk_sentences, current_chars
        chunk_text = " ".join(current_chunk_sentences)
        current_chunk_sentences = []
        current_chars = 0
        return chunk_text

    for sentence in sentences:
        sentence_chars = len(sentence)

        # If a single sentence exceeds max_chars, force-split at word boundary
        if sentence_chars > max_chars:
            if current_chunk_sentences:
                chunks.append(flush())

            words = sentence.split()
            word_buffer: list[str] = []
            word_buffer_chars = 0
            for word in words:
                wc = len(word) + 1  # +1 for space
                if word_buffer_chars + wc > max_chars and word_buffer:
                    chunks.append(" ".join(word_buffer) + " [...]")
                    # Overlap: keep last ~overlap_chars worth of words
                    overlap_buffer: list[str] = []
                    overlap_len = 0
                    for w in reversed(word_buffer):
                        if overlap_len + len(w) + 1 > overlap_chars:
                            break
                        overlap_buffer.insert(0, w)
                        overlap_len += len(w) + 1
                    word_buffer = overlap_buffer
                    word_buffer_chars = overlap_len
                word_buffer.append(word)
                word_buffer_chars += wc
            if word_buffer:
                chunks.append(" ".join(word_buffer))
            continue

        # Normal flow: add sentence to current chunk
        if current_chars + sentence_chars + 1 > max_chars and current_chunk_sentences:
            chunks.append(flush())
            # Apply overlap from previous chunk
            if overlap_chars > 0 and chunks:
                prev = chunks[-1]
                overlap_text = _extract_overlap(prev, overlap_chars)
                if overlap_text:
                    current_chunk_sentences.append(overlap_text)
                    current_chars = len(overlap_text)

        current_chunk_sentences.append(sentence)
        current_chars += sentence_chars + 1

    if current_chunk_sentences:
        chunks.append(flush())

    return [c for c in chunks if c.strip()]


def _extract_overlap(text: str, overlap_chars: int) -> str:
    """Extract the trailing *overlap_chars* from *text*, snapping to word boundary."""
    if len(text) <= overlap_chars:
        return text
    substring = text[-overlap_chars:]
    first_space = substring.find(" ")
    if first_space != -1:
        return substring[first_space + 1 :]
    return substring
