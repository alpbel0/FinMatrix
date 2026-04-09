"""BIST index provider adapter - isolates borsapy internal imports.

This module provides a clean interface for getting BIST 100 index constituents,
abstracting away the internal borsapy implementation details.
"""

from typing import Any

# Lazy-loaded provider instance
_bist_provider: Any = None


def _get_bist_provider() -> Any:
    """Lazy-load borsapy BIST index provider.

    Lazy loading avoids startup dependency issues if borsapy is not installed
    or network is unavailable during import.
    """
    global _bist_provider
    if _bist_provider is None:
        from borsapy._providers.bist_index import get_bist_index_provider

        _bist_provider = get_bist_index_provider()
    return _bist_provider


def get_bist100_symbols() -> list[str]:
    """Get BIST 100 index constituent stock symbols.

    Fetches the current BIST 100 components from BIST's official CSV
    via borsapy's BistIndexProvider.

    Returns:
        List of stock symbols (e.g., ["THYAO", "GARAN", "AKBNK", ...]).
        Empty list if fetch fails.

    Example:
        >>> symbols = get_bist100_symbols()
        >>> len(symbols)
        100
        >>> "THYAO" in symbols
        True
    """
    try:
        provider = _get_bist_provider()
        components = provider.get_components("XU100")
        return [c["symbol"] for c in components]
    except Exception:
        # Return empty list on failure - caller should handle gracefully
        return []


def is_symbol_in_bist100(symbol: str) -> bool:
    """Check if a stock symbol is in the BIST 100 index.

    Args:
        symbol: Stock symbol to check (e.g., "THYAO").

    Returns:
        True if symbol is in BIST 100, False otherwise.

    Example:
        >>> is_symbol_in_bist100("THYAO")
        True
        >>> is_symbol_in_bist100("UNKNOWN")
        False
    """
    try:
        provider = _get_bist_provider()
        return provider.is_in_index(symbol.upper(), "XU100")
    except Exception:
        return False


def get_indices_for_symbol(symbol: str) -> list[str]:
    """Get all BIST indices that contain a given stock.

    Args:
        symbol: Stock symbol to check (e.g., "THYAO").

    Returns:
        List of index symbols (e.g., ["XU030", "XU100", "XU BANK", ...]).

    Example:
        >>> get_indices_for_symbol("THYAO")
        ['XU030', 'XU100', ...]
    """
    try:
        provider = _get_bist_provider()
        return provider.get_indices_for_ticker(symbol.upper())
    except Exception:
        return []