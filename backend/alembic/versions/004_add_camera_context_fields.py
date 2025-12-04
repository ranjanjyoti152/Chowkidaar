"""Add camera context fields for intelligent severity

Revision ID: 004
Revises: 003
Create Date: 2025-12-04

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '004'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add context-aware detection fields to cameras table
    op.add_column('cameras', sa.Column('location_type', sa.String(100), nullable=True))
    op.add_column('cameras', sa.Column('expected_activity', sa.Text(), nullable=True))
    op.add_column('cameras', sa.Column('unexpected_activity', sa.Text(), nullable=True))
    op.add_column('cameras', sa.Column('normal_conditions', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('cameras', 'normal_conditions')
    op.drop_column('cameras', 'unexpected_activity')
    op.drop_column('cameras', 'expected_activity')
    op.drop_column('cameras', 'location_type')
