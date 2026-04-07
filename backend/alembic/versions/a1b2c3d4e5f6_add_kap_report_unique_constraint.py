"""add_kap_report_unique_constraint

Revision ID: a1b2c3d4e5f6
Revises: f8ada4730564
Create Date: 2026-04-07 22:00:00.000000
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'f8ada4730564'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add unique constraint for KAP report deduplication
    # This prevents duplicate filings from being inserted based on (stock_id, source_url)
    op.create_unique_constraint(
        "uq_kap_report_stock_source",
        "kap_reports",
        ["stock_id", "source_url"]
    )


def downgrade() -> None:
    # Remove the unique constraint
    op.drop_constraint("uq_kap_report_stock_source", "kap_reports", type_="unique")