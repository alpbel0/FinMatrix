"""Unit tests for bist_index_provider module."""

import pytest
from unittest.mock import patch, MagicMock

from app.services.data.providers.bist_index_provider import (
    get_bist100_symbols,
    is_symbol_in_bist100,
    get_indices_for_symbol,
    _get_bist_provider,
)


class TestGetBistProvider:
    """Tests for _get_bist_provider function."""

    def test_lazy_loads_provider(self):
        """Should lazy load the provider on first call."""
        # Reset the global provider
        import app.services.data.providers.bist_index_provider as module

        module._bist_provider = None

        with patch(
            "borsapy._providers.bist_index.get_bist_index_provider"
        ) as mock_get:
            mock_provider = MagicMock()
            mock_get.return_value = mock_provider

            result = _get_bist_provider()

            assert result == mock_provider
            mock_get.assert_called_once()

    def test_caches_provider(self):
        """Should cache the provider for subsequent calls."""
        import app.services.data.providers.bist_index_provider as module

        module._bist_provider = None

        with patch(
            "borsapy._providers.bist_index.get_bist_index_provider"
        ) as mock_get:
            mock_provider = MagicMock()
            mock_get.return_value = mock_provider

            # Call twice
            _get_bist_provider()
            _get_bist_provider()

            # Should only be called once (cached)
            mock_get.assert_called_once()


class TestGetBist100Symbols:
    """Tests for get_bist100_symbols function."""

    def test_returns_symbols_from_provider(self):
        """Should return list of symbols from provider."""
        mock_provider = MagicMock()
        mock_provider.get_components.return_value = [
            {"symbol": "THYAO", "name": "Turk Hava Yollari"},
            {"symbol": "GARAN", "name": "Garanti Bankasi"},
            {"symbol": "AKBNK", "name": "Akbank"},
        ]

        with patch(
            "app.services.data.providers.bist_index_provider._get_bist_provider",
            return_value=mock_provider,
        ):
            result = get_bist100_symbols()

            assert len(result) == 3
            assert "THYAO" in result
            assert "GARAN" in result
            assert "AKBNK" in result
            mock_provider.get_components.assert_called_once_with("XU100")

    def test_returns_empty_on_exception(self):
        """Should return empty list on provider exception."""
        mock_provider = MagicMock()
        mock_provider.get_components.side_effect = Exception("Network error")

        with patch(
            "app.services.data.providers.bist_index_provider._get_bist_provider",
            return_value=mock_provider,
        ):
            result = get_bist100_symbols()

            assert result == []

    def test_handles_empty_response(self):
        """Should handle empty response from provider."""
        mock_provider = MagicMock()
        mock_provider.get_components.return_value = []

        with patch(
            "app.services.data.providers.bist_index_provider._get_bist_provider",
            return_value=mock_provider,
        ):
            result = get_bist100_symbols()

            assert result == []


class TestIsSymbolInBist100:
    """Tests for is_symbol_in_bist100 function."""

    def test_returns_true_when_in_index(self):
        """Should return True when symbol is in BIST 100."""
        mock_provider = MagicMock()
        mock_provider.is_in_index.return_value = True

        with patch(
            "app.services.data.providers.bist_index_provider._get_bist_provider",
            return_value=mock_provider,
        ):
            result = is_symbol_in_bist100("THYAO")

            assert result is True
            mock_provider.is_in_index.assert_called_once_with("THYAO", "XU100")

    def test_returns_false_when_not_in_index(self):
        """Should return False when symbol is not in BIST 100."""
        mock_provider = MagicMock()
        mock_provider.is_in_index.return_value = False

        with patch(
            "app.services.data.providers.bist_index_provider._get_bist_provider",
            return_value=mock_provider,
        ):
            result = is_symbol_in_bist100("UNKNOWN")

            assert result is False

    def test_normalizes_to_uppercase(self):
        """Should normalize symbol to uppercase."""
        mock_provider = MagicMock()
        mock_provider.is_in_index.return_value = True

        with patch(
            "app.services.data.providers.bist_index_provider._get_bist_provider",
            return_value=mock_provider,
        ):
            is_symbol_in_bist100("thyao")

            mock_provider.is_in_index.assert_called_once_with("THYAO", "XU100")

    def test_returns_false_on_exception(self):
        """Should return False on provider exception."""
        mock_provider = MagicMock()
        mock_provider.is_in_index.side_effect = Exception("Error")

        with patch(
            "app.services.data.providers.bist_index_provider._get_bist_provider",
            return_value=mock_provider,
        ):
            result = is_symbol_in_bist100("THYAO")

            assert result is False


class TestGetIndicesForSymbol:
    """Tests for get_indices_for_symbol function."""

    def test_returns_indices_from_provider(self):
        """Should return list of indices from provider."""
        mock_provider = MagicMock()
        mock_provider.get_indices_for_ticker.return_value = ["XU030", "XU100", "XU BANK"]

        with patch(
            "app.services.data.providers.bist_index_provider._get_bist_provider",
            return_value=mock_provider,
        ):
            result = get_indices_for_symbol("THYAO")

            assert len(result) == 3
            assert "XU030" in result
            assert "XU100" in result
            mock_provider.get_indices_for_ticker.assert_called_once_with("THYAO")

    def test_returns_empty_on_exception(self):
        """Should return empty list on provider exception."""
        mock_provider = MagicMock()
        mock_provider.get_indices_for_ticker.side_effect = Exception("Error")

        with patch(
            "app.services.data.providers.bist_index_provider._get_bist_provider",
            return_value=mock_provider,
        ):
            result = get_indices_for_symbol("THYAO")

            assert result == []

    def test_normalizes_to_uppercase(self):
        """Should normalize symbol to uppercase."""
        mock_provider = MagicMock()
        mock_provider.get_indices_for_ticker.return_value = []

        with patch(
            "app.services.data.providers.bist_index_provider._get_bist_provider",
            return_value=mock_provider,
        ):
            get_indices_for_symbol("thyao")

            mock_provider.get_indices_for_ticker.assert_called_once_with("THYAO")