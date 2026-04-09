"""Add scheduler_settings table

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-04-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create scheduler_settings table
    op.create_table(
        "scheduler_settings",
        sa.Column("id", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "financial_reporting_mode", sa.Boolean(), nullable=False, server_default="false"
        ),
        sa.Column("financial_reporting_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("id = 1", name="ck_scheduler_settings_single_row"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Insert default row
    op.execute(
        """
        INSERT INTO scheduler_settings (id, financial_reporting_mode, financial_reporting_until, updated_at)
        VALUES (1, false, null, now())
        """
    )


def downgrade() -> None:
    op.drop_table("scheduler_settings")