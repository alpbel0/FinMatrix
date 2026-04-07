"""Mappers for financial statements."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from app.models.balance_sheet import BalanceSheet
from app.models.income_statement import IncomeStatement
from app.models.cash_flow import CashFlow
from app.services.data.provider_models import FinancialStatementSet, DataSource
from app.services.data.mappers.stock_price_mapper import get_stock_id_by_symbol


async def upsert_balance_sheet(
    db: AsyncSession,
    symbol: str,
    stmt: FinancialStatementSet,
) -> BalanceSheet | None:
    """
    Upsert balance sheet data.

    Uses ON CONFLICT on unique constraint (stock_id, period_type, statement_date, source)
    for deduplication.

    Args:
        db: AsyncSession instance
        symbol: Stock symbol
        stmt: Financial statement data from provider

    Returns:
        BalanceSheet model instance, or None if stock not found
    """
    stock_id = await get_stock_id_by_symbol(db, symbol)
    if stock_id is None:
        return None

    stmt_obj = insert(BalanceSheet).values(
        stock_id=stock_id,
        period_type=stmt.period_type.value,
        statement_date=stmt.statement_date,
        total_assets=stmt.total_assets,
        total_equity=stmt.total_equity,
        source=stmt.source.value,
    )

    stmt_obj = stmt_obj.on_conflict_do_update(
        constraint="uq_balance_sheet_version",
        set_={
            "total_assets": stmt_obj.excluded.total_assets,
            "total_equity": stmt_obj.excluded.total_equity,
        }
    ).returning(BalanceSheet)

    result = await db.execute(stmt_obj)
    await db.commit()
    return result.scalar_one_or_none()


async def upsert_income_statement(
    db: AsyncSession,
    symbol: str,
    stmt: FinancialStatementSet,
) -> IncomeStatement | None:
    """
    Upsert income statement data.

    Uses ON CONFLICT on unique constraint for deduplication.

    Args:
        db: AsyncSession instance
        symbol: Stock symbol
        stmt: Financial statement data from provider

    Returns:
        IncomeStatement model instance, or None if stock not found
    """
    stock_id = await get_stock_id_by_symbol(db, symbol)
    if stock_id is None:
        return None

    stmt_obj = insert(IncomeStatement).values(
        stock_id=stock_id,
        period_type=stmt.period_type.value,
        statement_date=stmt.statement_date,
        revenue=stmt.revenue,
        net_income=stmt.net_income,
        source=stmt.source.value,
    )

    stmt_obj = stmt_obj.on_conflict_do_update(
        constraint="uq_income_statement_version",
        set_={
            "revenue": stmt_obj.excluded.revenue,
            "net_income": stmt_obj.excluded.net_income,
        }
    ).returning(IncomeStatement)

    result = await db.execute(stmt_obj)
    await db.commit()
    return result.scalar_one_or_none()


async def upsert_cash_flow(
    db: AsyncSession,
    symbol: str,
    stmt: FinancialStatementSet,
) -> CashFlow | None:
    """
    Upsert cash flow data.

    Uses ON CONFLICT on unique constraint for deduplication.

    Args:
        db: AsyncSession instance
        symbol: Stock symbol
        stmt: Financial statement data from provider

    Returns:
        CashFlow model instance, or None if stock not found
    """
    stock_id = await get_stock_id_by_symbol(db, symbol)
    if stock_id is None:
        return None

    stmt_obj = insert(CashFlow).values(
        stock_id=stock_id,
        period_type=stmt.period_type.value,
        statement_date=stmt.statement_date,
        operating_cash_flow=stmt.operating_cash_flow,
        free_cash_flow=stmt.free_cash_flow,
        source=stmt.source.value,
    )

    stmt_obj = stmt_obj.on_conflict_do_update(
        constraint="uq_cash_flow_version",
        set_={
            "operating_cash_flow": stmt_obj.excluded.operating_cash_flow,
            "free_cash_flow": stmt_obj.excluded.free_cash_flow,
        }
    ).returning(CashFlow)

    result = await db.execute(stmt_obj)
    await db.commit()
    return result.scalar_one_or_none()


async def upsert_financial_statement_set(
    db: AsyncSession,
    symbol: str,
    stmt: FinancialStatementSet,
) -> dict[str, bool]:
    """
    Upsert complete financial statement set (all three statements).

    Convenience function that calls all three upsert functions.

    Args:
        db: AsyncSession instance
        symbol: Stock symbol
        stmt: Financial statement data from provider

    Returns:
        Dictionary with success status for each statement type
    """
    results = {}

    balance = await upsert_balance_sheet(db, symbol, stmt)
    results["balance_sheet"] = balance is not None

    income = await upsert_income_statement(db, symbol, stmt)
    results["income_statement"] = income is not None

    cashflow = await upsert_cash_flow(db, symbol, stmt)
    results["cash_flow"] = cashflow is not None

    return results