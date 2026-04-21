"""News API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session
from app.schemas.news import NewsListResponse, NewsReadRequest, NewsResponse
from app.services.auth_service import get_current_user
from app.services.news_service import (
    backfill_news_from_kap_reports,
    get_news_detail,
    get_news_feed,
    get_unread_count,
    get_user_news_status,
    mark_news_read,
)

router = APIRouter(prefix="/api/news", tags=["news"])
security = HTTPBearer()


@router.get("", response_model=NewsListResponse)
async def list_news(
    category: str | None = Query(None, description="Filter by category: financial_activity, kap_disclosures"),
    stock_id: int | None = Query(None, description="Filter by stock ID"),
    limit: int = Query(50, ge=1, le=100, description="Max items to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: AsyncSession = Depends(get_db_session),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Get news feed with optional filters.

    Each news item includes user-specific is_read status.
    Requires authentication via Bearer token.
    """
    user = await get_current_user(db, credentials.credentials)

    items = await get_news_feed(db, user.id, category, stock_id, limit, offset)
    if not items:
        await backfill_news_from_kap_reports(db)
        items = await get_news_feed(db, user.id, category, stock_id, limit, offset)

    unread_count = await get_unread_count(db, user.id, category, stock_id)

    response_items = []
    for item in items:
        user_news = await get_user_news_status(db, user.id, item.id)

        response_items.append(
            NewsResponse(
                id=item.id,
                stock_id=item.stock_id,
                symbol=item.stock.symbol if item.stock else None,
                title=item.title,
                category=item.category if item.category in {"financial_activity", "kap_disclosures"} else ("financial_activity" if item.filing_type in {"FR", "FAR"} else "kap_disclosures"),
                filing_type=item.filing_type,
                excerpt=item.excerpt,
                source_url=item.source_url,
                source_type=item.source_type,
                is_read=user_news.is_read if user_news else False,
                created_at=item.created_at,
            )
        )

    return NewsListResponse(
        items=response_items,
        total=len(response_items),
        unread_count=unread_count,
    )


@router.get("/{id}", response_model=NewsResponse)
async def get_news_item(
    id: int,
    db: AsyncSession = Depends(get_db_session),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Get single news item detail.

    Includes user-specific is_read status.
    Requires authentication via Bearer token.
    """
    user = await get_current_user(db, credentials.credentials)

    item = await get_news_detail(db, id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="News item not found",
        )

    user_news = await get_user_news_status(db, user.id, item.id)

    return NewsResponse(
        id=item.id,
        stock_id=item.stock_id,
        symbol=item.stock.symbol if item.stock else None,
        title=item.title,
        category=item.category if item.category in {"financial_activity", "kap_disclosures"} else ("financial_activity" if item.filing_type in {"FR", "FAR"} else "kap_disclosures"),
        filing_type=item.filing_type,
        excerpt=item.excerpt,
        source_url=item.source_url,
        source_type=item.source_type,
        is_read=user_news.is_read if user_news else False,
        created_at=item.created_at,
    )


@router.post("/{id}/read", response_model=NewsResponse)
async def mark_read(
    id: int,
    request: NewsReadRequest = NewsReadRequest(),
    db: AsyncSession = Depends(get_db_session),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Mark a news item as read/unread.

    Requires authentication via Bearer token.
    """
    user = await get_current_user(db, credentials.credentials)

    item = await get_news_detail(db, id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="News item not found",
        )

    await mark_news_read(db, user.id, id, request.is_read)

    return NewsResponse(
        id=item.id,
        stock_id=item.stock_id,
        symbol=item.stock.symbol if item.stock else None,
        title=item.title,
        category=item.category if item.category in {"financial_activity", "kap_disclosures"} else ("financial_activity" if item.filing_type in {"FR", "FAR"} else "kap_disclosures"),
        filing_type=item.filing_type,
        excerpt=item.excerpt,
        source_url=item.source_url,
        source_type=item.source_type,
        is_read=request.is_read,
        created_at=item.created_at,
    )
