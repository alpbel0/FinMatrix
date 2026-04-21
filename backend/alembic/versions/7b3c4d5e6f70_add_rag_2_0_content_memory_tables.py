"""add_rag_2_0_content_memory_tables

Revision ID: 7b3c4d5e6f70
Revises: 6a24b828fdb9
Create Date: 2026-04-21 21:20:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "7b3c4d5e6f70"
down_revision = "6a24b828fdb9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("kap_reports", sa.Column("rag_ingest_status", sa.String(length=50), nullable=False, server_default="PENDING"))
    op.add_column("kap_reports", sa.Column("rag_ingest_reason", sa.Text(), nullable=True))
    op.add_column("kap_reports", sa.Column("parser_version", sa.String(length=100), nullable=True))
    op.add_column("kap_reports", sa.Column("parsed_markdown_path", sa.String(length=500), nullable=True))

    op.create_table(
        "document_contents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("stock_id", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=128), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("content_markdown", sa.Text(), nullable=True),
        sa.Column("content_type", sa.String(length=50), nullable=False, server_default="paragraph"),
        sa.Column("content_origin", sa.String(length=50), nullable=False, server_default="pdf_docling"),
        sa.Column("section_path", sa.String(length=500), nullable=True),
        sa.Column("parser_version", sa.String(length=100), nullable=True),
        sa.Column("report_occurrence_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("first_seen_report_id", sa.Integer(), nullable=True),
        sa.Column("last_seen_report_id", sa.Integer(), nullable=True),
        sa.Column("embedding_status", sa.String(length=50), nullable=False, server_default="PENDING"),
        sa.Column("chroma_document_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["first_seen_report_id"], ["kap_reports.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["last_seen_report_id"], ["kap_reports.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["stock_id"], ["stocks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stock_id", "content_hash", name="uq_document_content_stock_hash"),
    )
    op.create_index("idx_document_contents_stock_created", "document_contents", ["stock_id", "created_at"], unique=False)

    op.create_table(
        "chunk_report_links",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("content_id", sa.Integer(), nullable=False),
        sa.Column("kap_report_id", sa.Integer(), nullable=False),
        sa.Column("stock_id", sa.Integer(), nullable=False),
        sa.Column("filing_type", sa.String(length=100), nullable=True),
        sa.Column("report_section", sa.String(length=500), nullable=True),
        sa.Column("element_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_summary_prefix", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("content_origin", sa.String(length=50), nullable=False, server_default="pdf_docling"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["content_id"], ["document_contents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["kap_report_id"], ["kap_reports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["stock_id"], ["stocks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("content_id", "kap_report_id", "element_order", name="uq_chunk_report_link_content_report_order"),
    )
    op.create_index("idx_chunk_report_links_stock_published", "chunk_report_links", ["stock_id", "published_at"], unique=False)
    op.create_index("idx_chunk_report_links_stock_filing_published", "chunk_report_links", ["stock_id", "filing_type", "published_at"], unique=False)
    op.create_index("idx_chunk_report_links_content_id", "chunk_report_links", ["content_id"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_chunk_report_links_content_id", table_name="chunk_report_links")
    op.drop_index("idx_chunk_report_links_stock_filing_published", table_name="chunk_report_links")
    op.drop_index("idx_chunk_report_links_stock_published", table_name="chunk_report_links")
    op.drop_table("chunk_report_links")

    op.drop_index("idx_document_contents_stock_created", table_name="document_contents")
    op.drop_table("document_contents")

    op.drop_column("kap_reports", "parsed_markdown_path")
    op.drop_column("kap_reports", "parser_version")
    op.drop_column("kap_reports", "rag_ingest_reason")
    op.drop_column("kap_reports", "rag_ingest_status")
