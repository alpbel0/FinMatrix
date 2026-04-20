"""Add graph debug fields to chat_traces.

Revision ID: c9d0e1f2a3b5
Revises: d4e5f6a7b8c9
Create Date: 2026-04-20
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "c9d0e1f2a3b5"
down_revision = "b9d0e1f2a3b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chat_traces",
        sa.Column(
            "graph_node_history",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "chat_traces",
        sa.Column("graph_fallback_reason", sa.String(length=100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("chat_traces", "graph_fallback_reason")
    op.drop_column("chat_traces", "graph_node_history")
