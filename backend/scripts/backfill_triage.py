"""Retroactive triage backfill script.

Run this once against existing document_contents to:
1. Classify existing rows with empty/missing section_path via deterministic rules
2. Set is_synthetic_section=True for rows that received a synthetic label
3. Populate processing_cache for future deduplication

Usage:
    cd backend && uv run python scripts/backfill_triage.py [--dry-run]
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from pathlib import Path

# Add backend to path so we can import app
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_maker
from app.models.document_content import DocumentContent
from app.models.processing_cache import ProcessingCache
from app.services.pipeline.triage_service import (
    _BLACKLIST_PATTERNS,
    _WHITELIST_PATTERNS,
    TriageDecision,
    _matches_any,
    _normalize_section_path,
)
from app.services.utils.logging import logger


_BATCH_SIZE = 500


def _deterministic_decision(section_path: str | None, text: str) -> tuple[TriageDecision, str | None]:
    """Apply deterministic triage rules to a single row."""
    section = (section_path or "").strip()

    # Blacklist
    if _matches_any(section, _BLACKLIST_PATTERNS):
        return TriageDecision.DISCARD, None

    # Whitelist
    if _matches_any(section, _WHITELIST_PATTERNS):
        return TriageDecision.KEEP, None

    # Quick discard
    if len(text.strip()) < 20 and not any(c.isalpha() for c in text):
        return TriageDecision.DISCARD, None

    # None section path -> would need LLM, but for backfill we keep them
    # and let future pipeline runs refine via cache
    if not section:
        return TriageDecision.KEEP, None

    # Unknown but non-empty section -> keep for now
    return TriageDecision.KEEP, None


async def backfill_triage(dry_run: bool = False) -> dict[str, int]:
    """Backfill triage decisions for existing document_contents."""
    stats = {"processed": 0, "updated": 0, "cache_created": 0, "skipped": 0}

    async with async_session_maker() as db:
        offset = 0
        while True:
            result = await db.execute(
                select(DocumentContent)
                .order_by(DocumentContent.id)
                .offset(offset)
                .limit(_BATCH_SIZE)
            )
            rows = result.scalars().all()
            if not rows:
                break

            for row in rows:
                stats["processed"] += 1
                decision, suggested = _deterministic_decision(
                    row.section_path, row.content_text or ""
                )

                if decision == TriageDecision.DISCARD:
                    # For retroactive backfill we don't delete rows,
                    # we just mark them so admin view can surface them
                    if not dry_run:
                        row.section_path = row.section_path or "DISCARDED"
                        row.is_synthetic_section = False
                        row.embedding_status = "SKIPPED"
                    stats["skipped"] += 1
                    continue

                # Check if we need to update is_synthetic_section
                needs_update = False
                if suggested and not row.is_synthetic_section:
                    needs_update = True
                    if not dry_run:
                        row.section_path = suggested
                        row.is_synthetic_section = True

                if needs_update:
                    stats["updated"] += 1

                # Ensure cache entry exists for the section_path
                cache_key = _normalize_section_path(row.section_path)
                if cache_key and not dry_run:
                    cache_exists = await db.execute(
                        select(ProcessingCache.id).where(
                            ProcessingCache.section_path == cache_key
                        )
                    )
                    if cache_exists.scalar_one_or_none() is None:
                        db.add(
                            ProcessingCache(
                                section_path=cache_key,
                                decision=decision.value,
                                suggested_label=suggested,
                                decided_by="backfill_script",
                            )
                        )
                        stats["cache_created"] += 1

            if not dry_run:
                await db.commit()

            offset += _BATCH_SIZE
            logger.info(f"Processed {stats['processed']} rows so far...")

    return stats


async def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill triage for existing document contents")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without writing to DB")
    args = parser.parse_args()

    logger.info(f"Starting backfill triage (dry_run={args.dry_run})")
    stats = await backfill_triage(dry_run=args.dry_run)
    logger.info(f"Backfill complete: {stats}")
    print(f"Backfill complete: {stats}")


if __name__ == "__main__":
    asyncio.run(main())
