"""add kap report pdf download fields

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-04-09
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a7b8c9d0e1f2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add PDF download tracking fields
    op.add_column("kap_reports", sa.Column("local_pdf_path", sa.String(500), nullable=True))
    op.add_column(
        "kap_reports",
        sa.Column("pdf_download_status", sa.String(50), server_default="PENDING", nullable=False),
    )
    op.add_column("kap_reports", sa.Column("pdf_file_size", sa.Integer(), nullable=True))
    op.add_column(
        "kap_reports",
        sa.Column("pdf_downloaded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("kap_reports", sa.Column("pdf_download_error", sa.Text(), nullable=True))

    # Create index for efficient query of pending downloads
    op.create_index("idx_kap_report_pdf_download_status", "kap_reports", ["pdf_download_status"])


def downgrade() -> None:
    op.drop_index("idx_kap_report_pdf_download_status", "kap_reports")
    op.drop_column("kap_reports", "pdf_download_error")
    op.drop_column("kap_reports", "pdf_downloaded_at")
    op.drop_column("kap_reports", "pdf_file_size")
    op.drop_column("kap_reports", "pdf_download_status")
    op.drop_column("kap_reports", "local_pdf_path")