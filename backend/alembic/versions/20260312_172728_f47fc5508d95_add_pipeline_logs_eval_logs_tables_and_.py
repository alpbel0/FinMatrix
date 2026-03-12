"""add pipeline_logs eval_logs tables and hallucination_reports view

Revision ID: f47fc5508d95
Revises: d818c713f889
Create Date: 2026-03-12 17:27:28.248966

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "f47fc5508d95"
down_revision: Union[str, None] = "d818c713f889"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create pipeline_status_enum
    pipeline_status_enum = postgresql.ENUM(
        "PENDING", "RUNNING", "SUCCESS", "FAILED",
        name="pipeline_status_enum",
        create_type=False,
    )
    pipeline_status_enum.create(op.get_bind(), checkfirst=True)

    # Create pipeline_logs table
    op.create_table(
        "pipeline_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            unique=True,
        ),
        sa.Column("pipeline_name", sa.String(100), nullable=False),
        sa.Column("job_name", sa.String(100), nullable=False),
        sa.Column("step_name", sa.String(100), nullable=True),
        sa.Column("stock_id", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            pipeline_status_enum,
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("processed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("details", postgresql.JSONB(), nullable=True),
        sa.ForeignKeyConstraint(["stock_id"], ["stocks.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_pipeline_logs_run_id", "pipeline_logs", ["run_id"])
    op.create_index("idx_pipeline_logs_status", "pipeline_logs", ["status"])

    # Create eval_logs table
    op.create_table(
        "eval_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("message_id", sa.Integer(), nullable=True),
        sa.Column("pipeline_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("bert_score", sa.Numeric(5, 4), nullable=True),
        sa.Column("rouge_score", sa.Numeric(5, 4), nullable=True),
        sa.Column("retrieval_score", sa.Numeric(5, 4), nullable=True),
        sa.Column("judge_model_used", sa.String(50), nullable=True),
        sa.Column("judge_reason", sa.Text(), nullable=True),
        sa.Column("is_hallucinated", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source_chunks_used", postgresql.JSONB(), nullable=True),
        sa.Column("details", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["message_id"], ["chat_messages.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["pipeline_run_id"], ["pipeline_logs.run_id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_eval_hallucinated", "eval_logs", ["is_hallucinated", "pipeline_run_id"]
    )
    op.create_index("idx_eval_logs_message", "eval_logs", ["message_id"])

    # Create hallucination_reports VIEW
    op.execute(
        """
        CREATE VIEW hallucination_reports AS
        SELECT
            id,
            message_id,
            pipeline_run_id,
            bert_score,
            rouge_score,
            retrieval_score,
            judge_model_used,
            judge_reason,
            retry_count,
            source_chunks_used,
            details,
            created_at
        FROM eval_logs
        WHERE is_hallucinated = TRUE
        """
    )


def downgrade() -> None:
    # Drop VIEW
    op.execute("DROP VIEW IF EXISTS hallucination_reports")

    # Drop eval_logs table
    op.drop_index("idx_eval_logs_message", table_name="eval_logs")
    op.drop_index("idx_eval_hallucinated", table_name="eval_logs")
    op.drop_table("eval_logs")

    # Drop pipeline_logs table
    op.drop_index("idx_pipeline_logs_status", table_name="pipeline_logs")
    op.drop_index("idx_pipeline_logs_run_id", table_name="pipeline_logs")
    op.drop_table("pipeline_logs")

    # Drop ENUM
    op.execute("DROP TYPE IF EXISTS pipeline_status_enum")