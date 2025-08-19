"""add_storage_expansion_history_to_pod

Revision ID: 84f8db892f3b
Revises: c3d824a79142
Create Date: 2025-08-18 23:49:17.252809

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '84f8db892f3b'
down_revision: Union[str, Sequence[str], None] = 'c3d824a79142'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('pod', sa.Column('storage_expansion_history', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('pod', 'storage_expansion_history')
