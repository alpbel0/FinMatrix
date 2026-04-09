"""Unit tests for symbol resolver.

Tests:
- DB lookup (exact match)
- Hardcoded alias map
- Normalization
- Null/empty handling
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.agents.symbol_resolver import (
    HARDCODED_ALIAS_MAP,
    normalize_symbol_input,
    resolve_symbol,
)


class TestNormalizeSymbolInput:
    """Tests for normalize_symbol_input function."""

    def test_uppercase_conversion(self):
        """Test lowercase to uppercase conversion."""
        assert normalize_symbol_input("thyao") == "THYAO"

    def test_whitespace_stripping(self):
        """Test whitespace stripping."""
        assert normalize_symbol_input("  THYAO  ") == "THYAO"

    def test_combined_normalization(self):
        """Test combined normalization."""
        assert normalize_symbol_input("  thy  ") == "THY"

    def test_none_input(self):
        """Test None input returns None."""
        assert normalize_symbol_input(None) is None

    def test_empty_string(self):
        """Test empty string returns None."""
        assert normalize_symbol_input("") is None

    def test_whitespace_only(self):
        """Test whitespace-only string returns None."""
        assert normalize_symbol_input("   ") is None


class TestHardcodedAliasMap:
    """Tests for hardcoded alias map."""

    def test_thy_alias(self):
        """Test THY -> THYAO mapping."""
        assert HARDCODED_ALIAS_MAP.get("THY") == "THYAO"

    def test_bim_alias(self):
        """Test BIM -> BIMAS mapping."""
        assert HARDCODED_ALIAS_MAP.get("BIM") == "BIMAS"

    def test_gar_alias(self):
        """Test GAR -> GARAN mapping."""
        assert HARDCODED_ALIAS_MAP.get("GAR") == "GARAN"

    def test_canonical_symbol_in_map(self):
        """Test that canonical symbols are also in the map."""
        assert HARDCODED_ALIAS_MAP.get("THYAO") == "THYAO"
        assert HARDCODED_ALIAS_MAP.get("BIMAS") == "BIMAS"

    def test_missing_alias(self):
        """Test missing alias returns None."""
        assert HARDCODED_ALIAS_MAP.get("NONEXISTENT") is None


class TestResolveSymbol:
    """Tests for resolve_symbol function."""

    @pytest.mark.asyncio
    async def test_none_candidate(self):
        """Test None candidate returns None."""
        db = AsyncMock()
        result = await resolve_symbol(db, None)
        assert result is None

    @pytest.mark.asyncio
    async def test_empty_candidate(self):
        """Test empty string candidate returns None."""
        db = AsyncMock()
        result = await resolve_symbol(db, "")
        assert result is None

    @pytest.mark.asyncio
    async def test_whitespace_candidate(self):
        """Test whitespace-only candidate returns None."""
        db = AsyncMock()
        result = await resolve_symbol(db, "   ")
        assert result is None

    @pytest.mark.asyncio
    async def test_db_exact_match(self):
        """Test DB exact match returns symbol."""
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = "THYAO"
        db.execute.return_value = mock_result

        result = await resolve_symbol(db, "THYAO")
        assert result == "THYAO"

    @pytest.mark.asyncio
    async def test_db_case_insensitive_query(self):
        """Test that query is normalized before DB lookup."""
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = "THYAO"
        db.execute.return_value = mock_result

        result = await resolve_symbol(db, "thyao")
        assert result == "THYAO"

    @pytest.mark.asyncio
    async def test_alias_fallback(self):
        """Test alias map fallback when DB returns None."""
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute.return_value = mock_result

        result = await resolve_symbol(db, "THY")
        assert result == "THYAO"

    @pytest.mark.asyncio
    async def test_not_found(self):
        """Test returns None when symbol not found anywhere."""
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute.return_value = mock_result

        result = await resolve_symbol(db, "NONEXISTENT")
        assert result is None

    @pytest.mark.asyncio
    async def test_db_error_fallback_to_alias(self):
        """Test alias fallback when DB throws error."""
        db = AsyncMock()
        db.execute.side_effect = Exception("DB error")

        result = await resolve_symbol(db, "THY")
        assert result == "THYAO"

    @pytest.mark.asyncio
    async def test_db_error_no_alias(self):
        """Test returns None when DB errors and no alias."""
        db = AsyncMock()
        db.execute.side_effect = Exception("DB error")

        result = await resolve_symbol(db, "NONEXISTENT")
        assert result is None