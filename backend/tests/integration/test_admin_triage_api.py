"""Integration tests for admin triage view API.

These tests are idempotent - they can be run multiple times against
the same database without failing."""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.main import app
from app.models.document_content import DocumentContent
from app.models.processing_cache import ProcessingCache
from app.models.stock import Stock
from app.models.user import User
from app.routers.admin import get_admin_user


@pytest.fixture
def admin_user() -> User:
    return User(
        id=999,
        username="admin",
        email="admin@test.com",
        password_hash="hash",
        is_admin=True,
    )


@pytest.fixture
def override_admin(admin_user):
    async def _override():
        return admin_user

    app.dependency_overrides[get_admin_user] = _override
    yield
    app.dependency_overrides.pop(get_admin_user, None)


async def _get_or_create_stock(db_session, symbol: str) -> Stock:
    """Get existing stock or create a new one."""
    result = await db_session.execute(select(Stock).where(Stock.symbol == symbol))
    stock = result.scalar_one_or_none()
    if stock:
        return stock
    stock = Stock(
        symbol=symbol,
        company_name=f"Company {symbol}",
        sector="Test",
        exchange="BIST",
        is_active=True,
    )
    db_session.add(stock)
    await db_session.flush()
    return stock


class TestAdminTriageApi:
    @pytest.mark.asyncio
    async def test_triage_view_returns_cache_and_synthetic(self, client, db_session, override_admin):
        # Use a unique section path to avoid conflicts
        unique_prefix = f"test_{uuid.uuid4().hex[:8]}"

        stock = await _get_or_create_stock(db_session, "THYAO")

        # Setup cache entries with unique names
        db_session.add(
            ProcessingCache(
                section_path=f"{unique_prefix}_bilanço",
                decision="KEEP",
                decided_by="triage_llm",
                decided_at=datetime(2026, 4, 20, 10, 0, tzinfo=timezone.utc),
            )
        )
        db_session.add(
            ProcessingCache(
                section_path=f"{unique_prefix}_kapak",
                decision="DISCARD",
                decided_by="triage_llm",
                decided_at=datetime(2026, 4, 20, 10, 1, tzinfo=timezone.utc),
            )
        )

        # Setup synthetic content
        db_session.add(
            DocumentContent(
                stock_id=stock.id,
                content_hash=f"{unique_prefix}_abc123",
                content_text="Net kar 5 milyar TL.",
                content_markdown="Net kar 5 milyar TL.",
                content_type="paragraph",
                section_path=f"{unique_prefix}_Finansal Özet",
                is_synthetic_section=True,
                embedding_status="PENDING",
            )
        )
        # Non-synthetic content
        db_session.add(
            DocumentContent(
                stock_id=stock.id,
                content_hash=f"{unique_prefix}_def456",
                content_text="Bilanço detayları.",
                content_markdown="Bilanço detayları.",
                content_type="table",
                section_path=f"{unique_prefix}_Bilanço",
                is_synthetic_section=False,
                embedding_status="PENDING",
            )
        )
        await db_session.commit()

        response = await client.get(
            "/api/admin/triage",
            headers={"Authorization": "Bearer test-token"},
        )

        assert response.status_code == 200
        payload = response.json()

        # Cache decisions should include our unique entries
        cache_sections = {d["section_path"] for d in payload["cache_decisions"]}
        assert f"{unique_prefix}_bilanço" in cache_sections
        assert f"{unique_prefix}_kapak" in cache_sections

        # Stats should be > 0
        stats = payload["stats"]
        assert stats["total_cache_entries"] >= 2
        assert stats["keep_count"] >= 1
        assert stats["discard_count"] >= 1

    @pytest.mark.asyncio
    async def test_triage_view_synthetic_only_filter(self, client, db_session, override_admin):
        unique_prefix = f"syn_{uuid.uuid4().hex[:8]}"
        stock = await _get_or_create_stock(db_session, "GARAN")

        db_session.add(
            DocumentContent(
                stock_id=stock.id,
                content_hash=f"{unique_prefix}_abc",
                content_text="Synthetic text",
                content_markdown="Synthetic text",
                content_type="paragraph",
                section_path=f"{unique_prefix}_AI Label",
                is_synthetic_section=True,
                embedding_status="PENDING",
            )
        )
        db_session.add(
            DocumentContent(
                stock_id=stock.id,
                content_hash=f"{unique_prefix}_def",
                content_text="Real text",
                content_markdown="Real text",
                content_type="paragraph",
                section_path=f"{unique_prefix}_Bilanço",
                is_synthetic_section=False,
                embedding_status="PENDING",
            )
        )
        await db_session.commit()

        response = await client.get(
            "/api/admin/triage?synthetic_only=true",
            headers={"Authorization": "Bearer test-token"},
        )

        assert response.status_code == 200
        payload = response.json()
        # Should find at least our synthetic entry
        synthetic_sections = [s["section_path"] for s in payload["synthetic_contents"] if s["is_synthetic_section"]]
        assert any(unique_prefix in s for s in synthetic_sections)

    @pytest.mark.asyncio
    async def test_triage_view_decision_filter(self, client, db_session, override_admin):
        unique_prefix = f"dec_{uuid.uuid4().hex[:8]}"

        db_session.add(
            ProcessingCache(
                section_path=f"{unique_prefix}_keep",
                decision="KEEP",
                decided_by="triage_llm",
            )
        )
        db_session.add(
            ProcessingCache(
                section_path=f"{unique_prefix}_discard",
                decision="DISCARD",
                decided_by="triage_llm",
            )
        )
        await db_session.commit()

        response = await client.get(
            f"/api/admin/triage?decision=KEEP&search={unique_prefix}",
            headers={"Authorization": "Bearer test-token"},
        )

        assert response.status_code == 200
        payload = response.json()
        assert len(payload["cache_decisions"]) >= 1
        assert all(d["decision"] == "KEEP" for d in payload["cache_decisions"])
        assert any(unique_prefix in d["section_path"] for d in payload["cache_decisions"])

    @pytest.mark.asyncio
    async def test_triage_view_search_filter(self, client, db_session, override_admin):
        unique_prefix = f"src_{uuid.uuid4().hex[:8]}"
        stock = await _get_or_create_stock(db_session, "ASELS")

        db_session.add(
            ProcessingCache(
                section_path=f"{unique_prefix}_bilanço detayları",
                decision="KEEP",
                decided_by="triage_llm",
            )
        )
        db_session.add(
            DocumentContent(
                stock_id=stock.id,
                content_hash=f"{unique_prefix}_abc",
                content_text="Bilanço detayları burada.",
                content_markdown="Bilanço detayları burada.",
                content_type="paragraph",
                section_path=f"{unique_prefix}_Bilanço",
                is_synthetic_section=False,
                embedding_status="PENDING",
            )
        )
        await db_session.commit()

        response = await client.get(
            f"/api/admin/triage?search={unique_prefix}",
            headers={"Authorization": "Bearer test-token"},
        )

        assert response.status_code == 200
        payload = response.json()
        assert len(payload["cache_decisions"]) >= 1
        assert len(payload["synthetic_contents"]) >= 1

    @pytest.mark.asyncio
    async def test_triage_view_pagination(self, client, db_session, override_admin):
        unique_prefix = f"pag_{uuid.uuid4().hex[:8]}"
        for i in range(5):
            db_session.add(
                ProcessingCache(
                    section_path=f"{unique_prefix}_section_{i}",
                    decision="KEEP",
                    decided_by="triage_llm",
                )
            )
        await db_session.commit()

        response = await client.get(
            f"/api/admin/triage?limit=2&offset=0&search={unique_prefix}",
            headers={"Authorization": "Bearer test-token"},
        )

        assert response.status_code == 200
        payload = response.json()
        assert len(payload["cache_decisions"]) == 2

    @pytest.mark.asyncio
    async def test_triage_view_stats_increase(self, client, db_session, override_admin):
        """Verify that stats reflect accumulated data."""
        unique_prefix = f"stat_{uuid.uuid4().hex[:8]}"

        # Get initial stats
        response = await client.get(
            "/api/admin/triage",
            headers={"Authorization": "Bearer test-token"},
        )
        initial_stats = response.json()["stats"]
        initial_total = initial_stats["total_cache_entries"]
        initial_synthetic = initial_stats["synthetic_count"]

        # Add new entries
        db_session.add(
            ProcessingCache(
                section_path=f"{unique_prefix}_new",
                decision="KEEP",
                decided_by="triage_llm",
            )
        )
        stock = await _get_or_create_stock(db_session, "KCHOL")
        db_session.add(
            DocumentContent(
                stock_id=stock.id,
                content_hash=f"{unique_prefix}_xyz",
                content_text="Test content",
                content_markdown="Test content",
                content_type="paragraph",
                section_path=f"{unique_prefix}_Synthetic",
                is_synthetic_section=True,
                embedding_status="PENDING",
            )
        )
        await db_session.commit()

        # Verify stats increased
        response = await client.get(
            "/api/admin/triage",
            headers={"Authorization": "Bearer test-token"},
        )
        new_stats = response.json()["stats"]
        assert new_stats["total_cache_entries"] > initial_total
        assert new_stats["synthetic_count"] > initial_synthetic
