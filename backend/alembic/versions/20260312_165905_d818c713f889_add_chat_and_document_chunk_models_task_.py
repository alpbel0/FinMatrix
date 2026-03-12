"""add chat and document chunk models (Task 2.6)

Revision ID: d818c713f889
Revises: 95be9d884fbd
Create Date: 2026-03-12 16:59:05.496175

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d818c713f889"
down_revision: Union[str, None] = "95be9d884fbd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create ENUMs for chat models
    message_role_enum = postgresql.ENUM(
        "user", "assistant", "system", name="message_role_enum", create_type=False
    )
    message_role_enum.create(op.get_bind(), checkfirst=True)

    message_type_enum = postgresql.ENUM(
        "text", "chart", "table", "system", name="message_type_enum", create_type=False
    )
    message_type_enum.create(op.get_bind(), checkfirst=True)

    embedding_status_enum = postgresql.ENUM(
        "PENDING", "SUCCESS", "FAILED", name="embedding_status_enum", create_type=False
    )
    embedding_status_enum.create(op.get_bind(), checkfirst=True)

    # Create chat_sessions table
    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "user_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_chat_sessions_user", "chat_sessions", ["user_id"])
    op.create_index("idx_chat_sessions_updated", "chat_sessions", ["updated_at"])

    # Create chat_messages table
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "session_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "role",
            postgresql.ENUM(
                "user", "assistant", "system", name="message_role_enum", create_type=False
            ),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "message_type",
            postgresql.ENUM(
                "text", "chart", "table", "system", name="message_type_enum", create_type=False
            ),
            nullable=False,
        ),
        sa.Column("extra_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("sources", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["chat_sessions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_chat_messages_session", "chat_messages", ["session_id", "timestamp"]
    )

    # Create document_chunks table
    op.create_table(
        "document_chunks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "kap_report_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("chunk_text_hash", sa.String(length=64), nullable=False),
        sa.Column("chroma_document_id", sa.String(length=100), nullable=True),
        sa.Column(
            "embedding_status",
            postgresql.ENUM(
                "PENDING", "SUCCESS", "FAILED", name="embedding_status_enum", create_type=False
            ),
            server_default="PENDING",
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["kap_report_id"],
            ["kap_reports.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "kap_report_id", "chunk_index", name="uq_document_chunks_report_index"
        ),
    )
    op.create_index("idx_document_chunks_report", "document_chunks", ["kap_report_id"])


def downgrade() -> None:
    # Drop document_chunks table
    op.drop_index("idx_document_chunks_report", table_name="document_chunks")
    op.drop_table("document_chunks")

    # Drop chat_messages table
    op.drop_index("idx_chat_messages_session", table_name="chat_messages")
    op.drop_table("chat_messages")

    # Drop chat_sessions table
    op.drop_index("idx_chat_sessions_updated", table_name="chat_sessions")
    op.drop_index("idx_chat_sessions_user", table_name="chat_sessions")
    op.drop_table("chat_sessions")

    # Drop ENUMs
    op.execute("DROP TYPE IF EXISTS embedding_status_enum")
    op.execute("DROP TYPE IF EXISTS message_type_enum")
    op.execute("DROP TYPE IF EXISTS message_role_enum")