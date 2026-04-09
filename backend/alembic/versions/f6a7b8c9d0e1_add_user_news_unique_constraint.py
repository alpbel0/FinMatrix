"""add user news unique constraint

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-04-09
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_user_news_user_id_news_id",
        "user_news",
        ["user_id", "news_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_user_news_user_id_news_id", "user_news", type_="unique")
