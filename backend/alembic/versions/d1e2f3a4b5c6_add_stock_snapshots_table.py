"""Add stock_snapshots table.

Revision ID: d1e2f3a4b5c6
Revises: c9d0e1f2a3b5
Create Date: 2026-04-21
"""

from alembic import op
import sqlalchemy as sa


revision = "d1e2f3a4b5c6"
down_revision = "c9d0e1f2a3b5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stock_snapshots",
        sa.Column("stock_id", sa.Integer(), sa.ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("pe_ratio", sa.Float(), nullable=True),
        sa.Column("pb_ratio", sa.Float(), nullable=True),
        sa.Column("dividend_yield", sa.Float(), nullable=True),
        sa.Column("trailing_eps", sa.Float(), nullable=True),
        sa.Column("roe", sa.Float(), nullable=True),
        sa.Column("debt_equity", sa.Float(), nullable=True),
        sa.Column("revenue_growth", sa.Float(), nullable=True),
        sa.Column("net_profit_growth", sa.Float(), nullable=True),
        sa.Column("foreign_ratio", sa.Float(), nullable=True),
        sa.Column("free_float", sa.Float(), nullable=True),
        sa.Column("year_high", sa.Float(), nullable=True),
        sa.Column("year_low", sa.Float(), nullable=True),
        sa.Column("ma_50", sa.Float(), nullable=True),
        sa.Column("ma_200", sa.Float(), nullable=True),
        sa.Column("market_cap", sa.Float(), nullable=True),
        sa.Column("last_price", sa.Float(), nullable=True),
        sa.Column("daily_volume", sa.Float(), nullable=True),
        sa.Column("source", sa.String(length=100), nullable=False, server_default="borsapy"),
        sa.Column("missing_fields_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completeness_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("is_partial", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("stock_id", "snapshot_date"),
    )
    op.create_index("idx_stock_snapshots_stock_date", "stock_snapshots", ["stock_id", "snapshot_date"])
    op.create_index("idx_stock_snapshots_snapshot_date", "stock_snapshots", ["snapshot_date"])


def downgrade() -> None:
    op.drop_index("idx_stock_snapshots_snapshot_date", table_name="stock_snapshots")
    op.drop_index("idx_stock_snapshots_stock_date", table_name="stock_snapshots")
    op.drop_table("stock_snapshots")
