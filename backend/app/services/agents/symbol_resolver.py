"""Symbol resolver for converting user input to canonical stock symbols.

This module handles the conversion of user-provided symbol candidates
to canonical database symbols using exact matching and a fallback alias map.

Key functions:
- resolve_symbol: Convert candidate symbol to canonical symbol
- HARDCODED_ALIAS_MAP: Common symbol aliases for fallback
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stock import Stock
from app.services.utils.logging import logger

# ============================================================================
# Hardcoded Alias Map
# ============================================================================

# Top common aliases for BIST stocks
# These map common abbreviations to canonical symbols
HARDCODED_ALIAS_MAP: dict[str, str] = {
    # Airlines
    "THY": "THYAO",
    "THYAO": "THYAO",
    # Banks
    "GAR": "GARAN",
    "GARAN": "GARAN",
    "AKB": "AKBNK",
    "AKBNK": "AKBNK",
    "ISB": "ISCTR",
    "ISCTR": "ISCTR",
    "VAKB": "VAKBN",
    "VAKBN": "VAKBN",
    "HALK": "HALKB",
    "HALKB": "HALKB",
    "YKB": "YKBNK",
    "YKBNK": "YKBNK",
    "SKB": "SKBNK",
    "SKBNK": "SKBNK",
    # Retail
    "BIM": "BIMAS",
    "BIMAS": "BIMAS",
    "MGRS": "MGROS",
    "MGROS": "MGROS",
    # Defense & Tech
    "ASEL": "ASELS",
    "ASELS": "ASELS",
    "TCELL": "TCELL",
    "TKF": "TKFEN",
    "TKFEN": "TKFEN",
    # Energy
    "TUPRS": "TUPRS",
    "EREGL": "EREGL",
    "TOAS": "TOASO",
    "TOASO": "TOASO",
    "FROTO": "FROTO",
    # Holding
    "KCHOL": "KCHOL",
    "SAHOL": "SAHOL",
    "EKGYO": "EKGYO",
}


# ============================================================================
# Core Functions
# ============================================================================


async def resolve_symbol(
    db: AsyncSession,
    candidate_symbol: str | None,
) -> str | None:
    """Convert candidate symbol to canonical DB symbol.

    Steps:
    1. Normalize: uppercase, strip whitespace
    2. DB lookup: exact match on symbol column
    3. Fallback: check HARDCODED_ALIAS_MAP

    NOTE: No company_name ILIKE search - avoid false positives on short tokens.

    Args:
        db: AsyncSession for database queries
        candidate_symbol: Raw symbol from user input (e.g., "thy", "bim")

    Returns:
        Canonical symbol (e.g., "THYAO", "BIMAS") or None if not found
    """
    if not candidate_symbol:
        return None

    # Step 1: Normalize
    normalized = candidate_symbol.upper().strip()

    if not normalized:
        return None

    # Step 2: Exact match in DB
    try:
        result = await db.execute(
            select(Stock.symbol).where(Stock.symbol == normalized)
        )
        db_symbol = result.scalar_one_or_none()
        if db_symbol:
            logger.debug(f"Symbol resolved from DB: {normalized} -> {db_symbol}")
            return db_symbol
    except Exception as e:
        logger.warning(f"DB lookup failed for symbol {normalized}: {e}")
        # Continue to fallback

    # Step 3: Alias map fallback
    alias_result = HARDCODED_ALIAS_MAP.get(normalized)
    if alias_result:
        logger.debug(f"Symbol resolved from alias map: {normalized} -> {alias_result}")
        return alias_result

    logger.debug(f"Symbol not found: {normalized}")
    return None


def normalize_symbol_input(symbol: str | None) -> str | None:
    """Normalize symbol input for display or storage.

    This is a utility function that only does string normalization
    without database lookup.

    Args:
        symbol: Raw symbol input

    Returns:
        Normalized (uppercase, stripped) symbol or None
    """
    if not symbol:
        return None
    normalized = symbol.upper().strip()
    return normalized if normalized else None