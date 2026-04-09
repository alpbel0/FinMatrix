"""Add chat_traces table for RAG pipeline debugging.

Revision ID: b9d0e1f2a3b4
Revises: a1b2c3d4e5f7
Create Date: 2026-04-09
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "b9d0e1f2a3b4"
down_revision = "a1b2c3d4e5f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chat_traces",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_message_id", sa.Integer(), sa.ForeignKey("chat_messages.id", ondelete="SET NULL"), nullable=True),
        sa.Column("assistant_message_id", sa.Integer(), sa.ForeignKey("chat_messages.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="STARTED"),
        sa.Column("original_query", sa.Text(), nullable=False),
        sa.Column("normalized_query", sa.Text(), nullable=True),
        sa.Column("candidate_symbol", sa.String(length=20), nullable=True),
        sa.Column("resolved_symbol", sa.String(length=20), nullable=True),
        sa.Column("document_type", sa.String(length=20), nullable=True),
        sa.Column("intent", sa.String(length=30), nullable=True),
        sa.Column("query_understanding_model", sa.String(length=200), nullable=True),
        sa.Column("response_model", sa.String(length=200), nullable=True),
        sa.Column("memory_context_preview", sa.Text(), nullable=True),
        sa.Column("retrieved_chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("retrieval_confidence", sa.Float(), nullable=True),
        sa.Column("context_total_chars", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("has_sufficient_context", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("sources_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("understanding_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("retrieval_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("response_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_chat_traces_session_created_at", "chat_traces", ["session_id", "created_at"])
    op.create_index("idx_chat_traces_user_created_at", "chat_traces", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("idx_chat_traces_user_created_at", table_name="chat_traces")
    op.drop_index("idx_chat_traces_session_created_at", table_name="chat_traces")
    op.drop_table("chat_traces")
