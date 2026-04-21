from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session
from app.schemas.stock import (
    HistoricalStockSnapshotPointResponse,
    HistoricalStockSnapshotResponse,
    PriceBarResponse,
    PriceHistoryResponse,
    StockSnapshotResponse,
    StockDetailResponse,
    StockListResponse,
    StockResponse,
)
from app.services.auth_service import get_current_user
from app.services.stock_service import (
    get_all_stocks,
    get_latest_stock_snapshot,
    get_price_history,
    get_stock_by_symbol,
    get_stock_snapshot_history,
)

router = APIRouter(prefix="/api/stocks", tags=["stocks"])
security = HTTPBearer()


@router.get("", response_model=StockListResponse)
async def list_stocks(
    search: str | None = Query(None, description="Filter stocks by symbol substring"),
    db: AsyncSession = Depends(get_db_session),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    List all active stocks with optional symbol search filter.

    Requires authentication via Bearer token.
    """
    # Verify token is valid
    await get_current_user(db, credentials.credentials)

    stocks = await get_all_stocks(db, search)
    return StockListResponse(
        stocks=[
            StockResponse(
                symbol=s.symbol,
                company_name=s.company_name,
                sector=s.sector,
            )
            for s in stocks
        ],
        total=len(stocks),
    )


@router.get("/{symbol}", response_model=StockDetailResponse)
async def get_stock_detail(
    symbol: str,
    db: AsyncSession = Depends(get_db_session),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Get detailed information for a single stock.

    Requires authentication via Bearer token.
    """
    # Verify token is valid
    await get_current_user(db, credentials.credentials)

    stock = await get_stock_by_symbol(db, symbol)
    if not stock:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stock '{symbol}' not found",
        )

    return StockDetailResponse(
        symbol=stock.symbol,
        company_name=stock.company_name,
        sector=stock.sector,
        exchange=stock.exchange,
        is_active=stock.is_active,
    )


@router.get("/{symbol}/prices", response_model=PriceHistoryResponse)
async def get_price_history_endpoint(
    symbol: str,
    start_date: date | None = Query(None, description="Start date filter (YYYY-MM-DD)"),
    end_date: date | None = Query(None, description="End date filter (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db_session),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Get price history for a stock.

    Returns OHLCV data ordered by date ascending.
    Requires authentication via Bearer token.
    """
    # Verify token is valid
    await get_current_user(db, credentials.credentials)

    # First verify stock exists
    stock = await get_stock_by_symbol(db, symbol)
    if not stock:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stock '{symbol}' not found",
        )

    prices = await get_price_history(db, symbol, start_date, end_date)
    return PriceHistoryResponse(
        symbol=symbol.upper(),
        prices=[
            PriceBarResponse(
                date=p.date,
                open=p.open,
                high=p.high,
                low=p.low,
                close=p.close,
                volume=p.volume,
            )
            for p in prices
        ],
        count=len(prices),
    )


@router.get("/{symbol}/snapshot/latest", response_model=StockSnapshotResponse)
async def get_latest_snapshot_endpoint(
    symbol: str,
    db: AsyncSession = Depends(get_db_session),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Get the most recent stored snapshot for a stock."""
    await get_current_user(db, credentials.credentials)

    stock = await get_stock_by_symbol(db, symbol)
    if not stock:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stock '{symbol}' not found",
        )

    payload = await get_latest_stock_snapshot(db, symbol)
    return StockSnapshotResponse(**payload)


@router.get("/{symbol}/snapshots", response_model=HistoricalStockSnapshotResponse)
async def get_snapshot_history_endpoint(
    symbol: str,
    start_date: date | None = Query(None, description="Start date filter (YYYY-MM-DD)"),
    end_date: date | None = Query(None, description="End date filter (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db_session),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Get historical snapshot time-series for a stock."""
    await get_current_user(db, credentials.credentials)

    stock = await get_stock_by_symbol(db, symbol)
    if not stock:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stock '{symbol}' not found",
        )

    payload = await get_stock_snapshot_history(db, symbol, start_date, end_date)
    return HistoricalStockSnapshotResponse(
        symbol=payload["symbol"],
        snapshots=[HistoricalStockSnapshotPointResponse(**item) for item in payload["snapshots"]],
        count=payload["count"],
    )
