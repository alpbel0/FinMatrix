"""add_advanced_metrics_and_sources_to_snapshots

Revision ID: 6a24b828fdb9
Revises: 2de76a87028a
Create Date: 2026-04-21 20:12:52.133154
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql



revision = '6a24b828fdb9'
down_revision = '2de76a87028a'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("balance_sheets", sa.Column("total_liabilities", sa.Float(), nullable=True))
    op.add_column("balance_sheets", sa.Column("current_assets", sa.Float(), nullable=True))
    op.add_column("balance_sheets", sa.Column("current_liabilities", sa.Float(), nullable=True))

    op.add_column("stock_snapshots", sa.Column("roa", sa.Float(), nullable=True))
    op.add_column("stock_snapshots", sa.Column("current_ratio", sa.Float(), nullable=True))
    op.add_column("stock_snapshots", sa.Column("field_sources", postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column("stock_snapshots", "field_sources")
    op.drop_column("stock_snapshots", "current_ratio")
    op.drop_column("stock_snapshots", "roa")

    op.drop_column("balance_sheets", "current_liabilities")
    op.drop_column("balance_sheets", "current_assets")
    op.drop_column("balance_sheets", "total_liabilities")
