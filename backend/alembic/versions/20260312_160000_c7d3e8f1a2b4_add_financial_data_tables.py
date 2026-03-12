"""add financial data tables

Revision ID: c7d3e8f1a2b4
Revises: ab8422a9cd54
Create Date: 2026-03-12 16:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "c7d3e8f1a2b4"
down_revision: Union[str, None] = "ab8422a9cd54"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create period_type ENUM
    period_type_enum = postgresql.ENUM(
        "Q1", "Q2", "Q3", "Q4", "ANNUAL", name="period_type_enum", create_type=False
    )
    period_type_enum.create(op.get_bind(), checkfirst=True)

    # Create stock_prices partitioned table (requires raw SQL)
    op.execute("""
        CREATE TABLE stock_prices (
            stock_id INTEGER NOT NULL,
            timestamp TIMESTAMPTZ NOT NULL,
            open NUMERIC(18,4) NOT NULL,
            high NUMERIC(18,4) NOT NULL,
            low NUMERIC(18,4) NOT NULL,
            close NUMERIC(18,4) NOT NULL,
            volume BIGINT NOT NULL,
            PRIMARY KEY (stock_id, timestamp)
        ) PARTITION BY RANGE (timestamp);
    """)

    # Create index on stock_prices
    op.execute("""
        CREATE INDEX idx_stock_prices_stock_time ON stock_prices (stock_id, timestamp);
    """)

    # Create default partition for safety (catches any data outside defined ranges)
    # Note: Actual monthly partitions should be created via create_partitions.py script
    op.execute("""
        CREATE TABLE stock_prices_default PARTITION OF stock_prices DEFAULT;
    """)

    # Create balance_sheets table
    op.create_table(
        "balance_sheets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("stock_id", sa.Integer(), nullable=False),
        sa.Column("period", period_type_enum, nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("fiscal_quarter", sa.Integer(), nullable=True),
        sa.Column("total_assets", sa.Numeric(20, 2), nullable=True),
        sa.Column("total_liabilities", sa.Numeric(20, 2), nullable=True),
        sa.Column("equity", sa.Numeric(20, 2), nullable=True),
        sa.Column("cash", sa.Numeric(20, 2), nullable=True),
        sa.Column("total_debt", sa.Numeric(20, 2), nullable=True),
        sa.ForeignKeyConstraint(["stock_id"], ["stocks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stock_id", "period", "date", name="uq_balance_sheet"),
    )
    op.create_index("idx_balance_sheets_stock", "balance_sheets", ["stock_id"])
    op.create_index("idx_balance_sheets_date", "balance_sheets", ["date"])

    # Create income_statements table
    op.create_table(
        "income_statements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("stock_id", sa.Integer(), nullable=False),
        sa.Column("period", period_type_enum, nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("fiscal_quarter", sa.Integer(), nullable=True),
        sa.Column("revenue", sa.Numeric(20, 2), nullable=True),
        sa.Column("net_income", sa.Numeric(20, 2), nullable=True),
        sa.Column("operating_income", sa.Numeric(20, 2), nullable=True),
        sa.Column("gross_profit", sa.Numeric(20, 2), nullable=True),
        sa.Column("ebitda", sa.Numeric(20, 2), nullable=True),
        sa.ForeignKeyConstraint(["stock_id"], ["stocks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stock_id", "period", "date", name="uq_income_statement"),
    )
    op.create_index("idx_income_statements_stock", "income_statements", ["stock_id"])
    op.create_index("idx_income_statements_date", "income_statements", ["date"])

    # Create cash_flows table
    op.create_table(
        "cash_flows",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("stock_id", sa.Integer(), nullable=False),
        sa.Column("period", period_type_enum, nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("fiscal_quarter", sa.Integer(), nullable=True),
        sa.Column("operating_cash_flow", sa.Numeric(20, 2), nullable=True),
        sa.Column("investing_cash_flow", sa.Numeric(20, 2), nullable=True),
        sa.Column("financing_cash_flow", sa.Numeric(20, 2), nullable=True),
        sa.Column("free_cash_flow", sa.Numeric(20, 2), nullable=True),
        sa.ForeignKeyConstraint(["stock_id"], ["stocks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stock_id", "period", "date", name="uq_cash_flow"),
    )
    op.create_index("idx_cash_flows_stock", "cash_flows", ["stock_id"])
    op.create_index("idx_cash_flows_date", "cash_flows", ["date"])


def downgrade() -> None:
    # Drop cash_flows
    op.drop_index("idx_cash_flows_date", table_name="cash_flows")
    op.drop_index("idx_cash_flows_stock", table_name="cash_flows")
    op.drop_table("cash_flows")

    # Drop income_statements
    op.drop_index("idx_income_statements_date", table_name="income_statements")
    op.drop_index("idx_income_statements_stock", table_name="income_statements")
    op.drop_table("income_statements")

    # Drop balance_sheets
    op.drop_index("idx_balance_sheets_date", table_name="balance_sheets")
    op.drop_index("idx_balance_sheets_stock", table_name="balance_sheets")
    op.drop_table("balance_sheets")

    # Drop stock_prices (partitioned table)
    op.execute("DROP TABLE IF EXISTS stock_prices CASCADE;")

    # Drop ENUM
    op.execute("DROP TYPE IF EXISTS period_type_enum;")