"""Add KapReport enrichment fields

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-04-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add enrichment fields to kap_reports table
    op.add_column('kap_reports', sa.Column('summary', sa.Text(), nullable=True))
    op.add_column('kap_reports', sa.Column('attachment_count', sa.Integer(), nullable=True))
    op.add_column('kap_reports', sa.Column('is_late', sa.Boolean(), nullable=True))
    op.add_column('kap_reports', sa.Column('related_stocks', postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    # Remove enrichment fields from kap_reports table
    op.drop_column('kap_reports', 'related_stocks')
    op.drop_column('kap_reports', 'is_late')
    op.drop_column('kap_reports', 'attachment_count')
    op.drop_column('kap_reports', 'summary')