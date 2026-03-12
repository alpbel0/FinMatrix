"""add KAP reports and news models (Task 2.5)

Revision ID: 95be9d884fbd
Revises: c7d3e8f1a2b4
Create Date: 2026-03-12 16:03:53.681881

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '95be9d884fbd'
down_revision: Union[str, None] = 'c7d3e8f1a2b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create ENUMs
    sync_status_enum = postgresql.ENUM(
        'PENDING', 'SUCCESS', 'FAILED',
        name='sync_status_enum',
        create_type=False
    )
    sync_status_enum.create(op.get_bind(), checkfirst=True)

    news_source_enum = postgresql.ENUM(
        'kap_summary', 'external_news', 'manual',
        name='news_source_enum',
        create_type=False
    )
    news_source_enum.create(op.get_bind(), checkfirst=True)

    # Create kap_reports table
    op.create_table(
        'kap_reports',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('stock_id', sa.Integer(), nullable=False),
        sa.Column('bildirim_no', sa.String(50), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('pdf_url', sa.String(500), nullable=True),
        sa.Column('published_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('fetched_date', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('chroma_sync_status', sync_status_enum, nullable=False, server_default='PENDING'),
        sa.Column('chunk_count', sa.Integer(), nullable=False, server_default='0'),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['stock_id'], ['stocks.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('bildirim_no')
    )
    op.create_index('idx_kap_reports_stock', 'kap_reports', ['stock_id'])
    op.create_index('idx_kap_reports_published', 'kap_reports', ['published_date'])

    # Create news table
    op.create_table(
        'news',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('stock_id', sa.Integer(), nullable=True),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('published_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('source_type', news_source_enum, nullable=False),
        sa.Column('source_ref_id', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['stock_id'], ['stocks.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['source_ref_id'], ['kap_reports.id'], ondelete='SET NULL')
    )
    op.create_index('idx_news_stock', 'news', ['stock_id'])
    op.create_index('idx_news_published', 'news', ['published_date'])
    op.create_index('idx_news_source_type', 'news', ['source_type'])

    # Create user_news table (composite primary key)
    op.create_table(
        'user_news',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('news_id', sa.Integer(), nullable=False),
        sa.Column('is_read', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('user_id', 'news_id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['news_id'], ['news.id'], ondelete='CASCADE')
    )
    op.create_index('idx_user_news_user', 'user_news', ['user_id'])


def downgrade() -> None:
    # Drop user_news table
    op.drop_index('idx_user_news_user', 'user_news')
    op.drop_table('user_news')

    # Drop news table
    op.drop_index('idx_news_source_type', 'news')
    op.drop_index('idx_news_published', 'news')
    op.drop_index('idx_news_stock', 'news')
    op.drop_table('news')

    # Drop kap_reports table
    op.drop_index('idx_kap_reports_published', 'kap_reports')
    op.drop_index('idx_kap_reports_stock', 'kap_reports')
    op.drop_table('kap_reports')

    # Drop ENUMs
    op.execute('DROP TYPE IF EXISTS news_source_enum')
    op.execute('DROP TYPE IF EXISTS sync_status_enum')
