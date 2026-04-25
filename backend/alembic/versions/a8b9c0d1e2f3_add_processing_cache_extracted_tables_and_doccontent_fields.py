"""Add processing_cache, extracted_tables, and document_content fields

Revision ID: a8b9c0d1e2f3
Revises: 7b3c4d5e6f70
Create Date: 2026-04-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a8b9c0d1e2f3"
down_revision: Union[str, None] = "7b3c4d5e6f70"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. extracted_tables
    # ------------------------------------------------------------------
    op.create_table(
        "extracted_tables",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("kap_report_id", sa.Integer(), nullable=False),
        sa.Column("section_path", sa.String(length=500), nullable=True),
        sa.Column("table_markdown", sa.Text(), nullable=False),
        sa.Column("table_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_extracted_tables")),
        sa.ForeignKeyConstraint(
            ["kap_report_id"],
            ["kap_reports.id"],
            name=op.f("fk_extracted_tables_kap_report_id_kap_reports"),
            ondelete="CASCADE",
        ),
        sa.Index("idx_extracted_tables_kap_report_id", "kap_report_id"),
    )

    # ------------------------------------------------------------------
    # 2. processing_cache
    # ------------------------------------------------------------------
    op.create_table(
        "processing_cache",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("section_path", sa.String(length=500), nullable=False),
        sa.Column("decision", sa.String(length=20), nullable=False),
        sa.Column("suggested_label", sa.String(length=500), nullable=True),
        sa.Column("decided_by", sa.String(length=50), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_processing_cache")),
        sa.UniqueConstraint("section_path", name=op.f("uq_processing_cache_section_path")),
    )

    # ------------------------------------------------------------------
    # 3. document_contents alterations
    # ------------------------------------------------------------------
    with op.batch_alter_table("document_contents", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "parent_content_id",
                sa.Integer(),
                sa.ForeignKey("document_contents.id", ondelete="CASCADE"),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "is_synthetic_section",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            )
        )
        batch_op.add_column(
            sa.Column(
                "processed_text",
                sa.Text(),
                nullable=True,
            )
        )
        batch_op.create_index("idx_document_contents_parent_id", ["parent_content_id"], unique=False)
        batch_op.create_index("idx_document_contents_synthetic", ["is_synthetic_section"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("document_contents", schema=None) as batch_op:
        batch_op.drop_index("idx_document_contents_synthetic")
        batch_op.drop_index("idx_document_contents_parent_id")
        batch_op.drop_column("processed_text")
        batch_op.drop_column("is_synthetic_section")
        batch_op.drop_column("parent_content_id")

    op.drop_table("processing_cache")
    op.drop_table("extracted_tables")
