"""Add unique constraint to stock_prices table

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-08

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add unique constraint on (stock_id, date) for upsert operations
    op.create_unique_constraint(
        "uq_stock_price_stock_date",
        "stock_prices",
        ["stock_id", "date"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_stock_price_stock_date",
        "stock_prices",
        type_="unique",
    )