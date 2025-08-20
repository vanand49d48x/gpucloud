"""merge heads

Revision ID: 8a10c52c3926
Revises: 84f8db892f3b, add_per_pod_iam_fields
Create Date: 2025-08-20 00:19:23.452488

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8a10c52c3926'
down_revision: Union[str, Sequence[str], None] = ('84f8db892f3b', 'add_per_pod_iam_fields')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
