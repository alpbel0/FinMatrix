"""Watchlist API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session
from app.schemas.watchlist import (
    NotificationToggleRequest,
    WatchlistAddRequest,
    WatchlistItemResponse,
    WatchlistListResponse,
)
from app.services.auth_service import get_current_user
from app.services.stock_service import get_stock_by_symbol
from app.services.watchlist_service import (
    add_to_watchlist,
    get_latest_price_for_stock,
    get_previous_price_for_stock,
    get_user_watchlist,
    remove_from_watchlist,
    toggle_notifications,
)

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])
security = HTTPBearer()


@router.get("", response_model=WatchlistListResponse)
async def list_watchlist(
    db: AsyncSession = Depends(get_db_session),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Get user's watchlist with stock info and latest prices.

    Requires authentication via Bearer token.
    """
    user = await get_current_user(db, credentials.credentials)
    items = await get_user_watchlist(db, user.id)

    response_items = []
    for item in items:
        latest_price = await get_latest_price_for_stock(db, item.stock_id)

        price_change = None
        price_change_percent = None
        price_date = None
        latest_close = None

        if latest_price and latest_price.close:
            latest_close = latest_price.close
            price_date = latest_price.date
            prev_price = await get_previous_price_for_stock(db, item.stock_id, latest_price.date)
            if prev_price and prev_price.close:
                price_change = latest_price.close - prev_price.close
                price_change_percent = (price_change / prev_price.close) * 100

        response_items.append(
            WatchlistItemResponse(
                id=item.id,
                symbol=item.stock.symbol,
                company_name=item.stock.company_name,
                sector=item.stock.sector,
                notifications_enabled=item.notifications_enabled,
                latest_price=latest_close,
                price_change=price_change,
                price_change_percent=price_change_percent,
                price_date=price_date,
                created_at=item.created_at,
            )
        )

    return WatchlistListResponse(items=response_items, total=len(response_items))


@router.post("", response_model=WatchlistItemResponse, status_code=status.HTTP_201_CREATED)
async def add_watchlist_item(
    request: WatchlistAddRequest,
    db: AsyncSession = Depends(get_db_session),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Add a stock to user's watchlist.

    Requires authentication via Bearer token.
    """
    user = await get_current_user(db, credentials.credentials)

    stock = await get_stock_by_symbol(db, request.symbol)
    if not stock:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stock '{request.symbol}' not found",
        )

    try:
        item = await add_to_watchlist(db, user.id, stock.id, request.notifications_enabled)
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Stock '{request.symbol}' already in watchlist",
        )

    # Get latest price for response
    latest_price = await get_latest_price_for_stock(db, stock.id)
    latest_close = latest_price.close if latest_price else None
    price_date = latest_price.date if latest_price else None

    return WatchlistItemResponse(
        id=item.id,
        symbol=stock.symbol,
        company_name=stock.company_name,
        sector=stock.sector,
        notifications_enabled=item.notifications_enabled,
        latest_price=latest_close,
        price_change=None,
        price_change_percent=None,
        price_date=price_date,
        created_at=item.created_at,
    )


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_watchlist_item(
    id: int,
    db: AsyncSession = Depends(get_db_session),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Remove a stock from user's watchlist.

    Requires authentication via Bearer token.
    """
    user = await get_current_user(db, credentials.credentials)

    removed = await remove_from_watchlist(db, id, user.id)
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Watchlist item not found",
        )


@router.patch("/{id}/notifications", response_model=WatchlistItemResponse)
async def update_notifications(
    id: int,
    request: NotificationToggleRequest,
    db: AsyncSession = Depends(get_db_session),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Toggle notifications for a watchlist item.

    Requires authentication via Bearer token.
    """
    user = await get_current_user(db, credentials.credentials)

    item = await toggle_notifications(db, id, user.id, request.notifications_enabled)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Watchlist item not found",
        )

    # Get latest price for response
    latest_price = await get_latest_price_for_stock(db, item.stock_id)
    latest_close = latest_price.close if latest_price else None
    price_date = latest_price.date if latest_price else None

    return WatchlistItemResponse(
        id=item.id,
        symbol=item.stock.symbol,
        company_name=item.stock.company_name,
        sector=item.stock.sector,
        notifications_enabled=item.notifications_enabled,
        latest_price=latest_close,
        price_change=None,
        price_change_percent=None,
        price_date=price_date,
        created_at=item.created_at,
    )