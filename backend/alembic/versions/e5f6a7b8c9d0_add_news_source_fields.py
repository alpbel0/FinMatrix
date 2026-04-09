"""add news source fields

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-04-09

Adds source_type, source_id, filing_type columns to news table
for KAP -> News transformation tracking with duplicate protection.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add source_type column (string: "kap", "manual", etc.)
    op.add_column("news", sa.Column("source_type", sa.String(length=50), nullable=True))

    # Add source_id column (int: reference to source table, e.g., kap_report.id)
    op.add_column("news", sa.Column("source_id", sa.Integer(), nullable=True))

    # Add filing_type column (raw filing type from KAP: "FR", "FAR", etc.)
    op.add_column("news", sa.Column("filing_type", sa.String(length=100), nullable=True))

    # Create unique constraint for duplicate protection
    # Same (source_type, source_id) combination should not produce multiple news items
    op.create_unique_constraint(
        "uq_news_source_type_source_id",
        "news",
        ["source_type", "source_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_news_source_type_source_id", "news", type_="unique")
    op.drop_column("news", "filing_type")
    op.drop_column("news", "source_id")
    op.drop_column("news", "source_type")