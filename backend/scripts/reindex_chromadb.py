"""Reindex missing completed chunks into ChromaDB.

Usage:
    python scripts/reindex_chromadb.py
    python scripts/reindex_chromadb.py --symbols THYAO,BIMAS

This script compares completed DB chunks against the current Chroma collection
and re-embeds only the missing document ids.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Sequence
from pathlib import Path

import httpx
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models.document_chunk import DocumentChunk
from app.models.kap_report import KapReport
from app.models.stock import Stock
from app.services.pipeline.embedding_service import (
    _build_chunk_metadata,
    _get_embeddings_from_openrouter,
    _get_or_create_collection,
)


def _parse_symbols(raw: str | None) -> set[str]:
    if not raw:
        return set()
    return {
        symbol.strip().upper()
        for symbol in raw.split(",")
        if symbol.strip()
    }


async def _fetch_missing_chunks(symbols: set[str]) -> list[tuple[DocumentChunk, KapReport, str]]:
    async with AsyncSessionLocal() as db:
        collection = _get_or_create_collection()
        existing_ids = set(collection.get(include=[])["ids"])

        query = (
            select(DocumentChunk, KapReport, Stock.symbol)
            .join(KapReport, KapReport.id == DocumentChunk.kap_report_id)
            .join(Stock, Stock.id == KapReport.stock_id)
            .where(DocumentChunk.embedding_status == "COMPLETED")
            .where(DocumentChunk.chunk_text_hash.is_not(None))
            .order_by(DocumentChunk.id)
        )
        if symbols:
            query = query.where(Stock.symbol.in_(symbols))

        rows = (await db.execute(query)).all()

        missing: list[tuple[DocumentChunk, KapReport, str]] = []
        for chunk, report, stock_symbol in rows:
            if not chunk.chunk_text_hash:
                continue
            if chunk.chunk_text_hash in existing_ids:
                continue
            missing.append((chunk, report, stock_symbol))

        return missing


async def _upsert_batches(rows: Sequence[tuple[DocumentChunk, KapReport, str]]) -> int:
    if not rows:
        return 0

    settings = get_settings()
    collection = _get_or_create_collection()
    processed = 0

    async with httpx.AsyncClient() as client:
        for start in range(0, len(rows), settings.embedding_batch_size):
            batch = rows[start:start + settings.embedding_batch_size]
            texts = [chunk.chunk_text for chunk, _, _ in batch]
            embeddings = await _get_embeddings_from_openrouter(
                texts=texts,
                client=client,
                api_key=settings.openrouter_api_key,
                timeout=settings.embedding_timeout,
            )
            collection.upsert(
                ids=[chunk.chunk_text_hash for chunk, _, _ in batch if chunk.chunk_text_hash],
                embeddings=embeddings,
                metadatas=[
                    _build_chunk_metadata(chunk, report, stock_symbol)
                    for chunk, report, stock_symbol in batch
                ],
                documents=texts,
            )
            processed += len(batch)

    return processed


async def main() -> None:
    parser = argparse.ArgumentParser(description="Reindex missing completed DB chunks into ChromaDB.")
    parser.add_argument("--symbols", help="Comma-separated stock symbols to limit the reindex scope.")
    args = parser.parse_args()

    symbols = _parse_symbols(args.symbols)
    missing_rows = await _fetch_missing_chunks(symbols)

    print(f"missing_chunks={len(missing_rows)}")
    if not missing_rows:
        return

    processed = await _upsert_batches(missing_rows)
    unique_symbols = sorted({stock_symbol for _, _, stock_symbol in missing_rows})

    print(f"reindexed_chunks={processed}")
    print(f"symbols={','.join(unique_symbols)}")


if __name__ == "__main__":
    asyncio.run(main())
