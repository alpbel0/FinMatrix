"""Add sources_metadata to chat_messages

Revision ID: a1b2c3d4e5f7
Revises: f6a7b8c9d0e1
Create Date: 2026-04-09

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f7"
down_revision = "b8c9d0e1f2a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add sources_metadata JSONB column to chat_messages table."""
    op.add_column(
        "chat_messages",
        sa.Column(
            "sources_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
    )


def downgrade() -> None:
    """Remove sources_metadata column from chat_messages table."""
    op.drop_column("chat_messages", "sources_metadata")
