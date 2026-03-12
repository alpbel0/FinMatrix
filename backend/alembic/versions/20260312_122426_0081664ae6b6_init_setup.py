"""init_setup

Revision ID: 0081664ae6b6
Revises: bacf28dc4d1a
Create Date: 2026-03-12 12:24:26.297404

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0081664ae6b6'
down_revision: Union[str, None] = 'bacf28dc4d1a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass