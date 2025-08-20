"""Add per-pod IAM and logging fields

Revision ID: add_per_pod_iam_fields
Revises: 
Create Date: 2025-01-15 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_per_pod_iam_fields'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns to the pod table
    op.add_column('pod', sa.Column('role_name', sa.String(), nullable=True))
    op.add_column('pod', sa.Column('role_arn', sa.String(), nullable=True))
    op.add_column('pod', sa.Column('instance_profile', sa.String(), nullable=True))
    op.add_column('pod', sa.Column('log_group', sa.String(), nullable=True))
    
    # Create indexes for better query performance
    op.create_index(op.f('ix_pod_role_name'), 'pod', ['role_name'], unique=False)
    op.create_index(op.f('ix_pod_log_group'), 'pod', ['log_group'], unique=False)


def downgrade() -> None:
    # Remove indexes
    op.drop_index(op.f('ix_pod_log_group'), table_name='pod')
    op.drop_index(op.f('ix_pod_role_name'), table_name='pod')
    
    # Remove columns
    op.drop_column('pod', 'log_group')
    op.drop_column('pod', 'instance_profile')
    op.drop_column('pod', 'role_arn')
    op.drop_column('pod', 'role_name')


