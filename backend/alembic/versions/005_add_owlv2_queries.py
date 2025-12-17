"""Add OWLv2 custom queries field

Revision ID: 005
Revises: 004_add_camera_context_fields
Create Date: 2024-01-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '005'
down_revision: Union[str, None] = '004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add owlv2_queries column for open-vocabulary detection queries
    op.add_column('user_settings', sa.Column(
        'owlv2_queries', 
        sa.JSON(), 
        nullable=True,
        server_default='["a person", "a car", "a fire", "a lighter", "a dog", "a cat", "a weapon", "a knife", "a suspicious object"]'
    ))


def downgrade() -> None:
    op.drop_column('user_settings', 'owlv2_queries')
