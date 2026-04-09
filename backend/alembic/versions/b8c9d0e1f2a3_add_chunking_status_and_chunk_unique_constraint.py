"""add chunking status and document chunk unique constraint

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-04-09
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b8c9d0e1f2a3"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # KapReport: Add chunking tracking fields
    op.add_column(
        "kap_reports",
        sa.Column("chunking_status", sa.String(50), server_default="PENDING", nullable=False),
    )
    op.add_column("kap_reports", sa.Column("chunking_error", sa.Text(), nullable=True))
    op.add_column(
        "kap_reports",
        sa.Column("chunked_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Create index for efficient query of pending chunking
    op.create_index("idx_kap_report_chunking_status", "kap_reports", ["chunking_status"])

    # DocumentChunk: Handle potential duplicates BEFORE adding constraint
    # Step: Delete duplicates, keeping the one with lowest id for each (kap_report_id, chunk_text_hash) pair
    # Only applies where chunk_text_hash is NOT NULL
    op.execute("""
        DELETE FROM document_chunks
        WHERE id IN (
            SELECT id FROM document_chunks
            WHERE chunk_text_hash IS NOT NULL
            AND id NOT IN (
                SELECT MIN(id) FROM document_chunks
                WHERE chunk_text_hash IS NOT NULL
                GROUP BY kap_report_id, chunk_text_hash
            )
        )
    """)

    # Add unique constraint for deduplication
    op.create_unique_constraint(
        "uq_document_chunk_report_hash",
        "document_chunks",
        ["kap_report_id", "chunk_text_hash"],
    )


def downgrade() -> None:
    # DocumentChunk: Drop unique constraint
    op.drop_constraint("uq_document_chunk_report_hash", "document_chunks", type_="unique")

    # KapReport: Drop chunking fields
    op.drop_index("idx_kap_report_chunking_status", "kap_reports")
    op.drop_column("kap_reports", "chunked_at")
    op.drop_column("kap_reports", "chunking_error")
    op.drop_column("kap_reports", "chunking_status")