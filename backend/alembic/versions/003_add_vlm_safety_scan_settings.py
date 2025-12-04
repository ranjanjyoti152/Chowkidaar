"""Add VLM safety scan settings

Revision ID: 003
Revises: 002
Create Date: 2024-12-04

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade():
    # Add VLM safety scan settings columns
    op.add_column('user_settings', sa.Column('vlm_safety_scan_enabled', sa.Boolean(), server_default='true', nullable=True))
    op.add_column('user_settings', sa.Column('vlm_safety_scan_interval', sa.Integer(), server_default='30', nullable=True))


def downgrade():
    op.drop_column('user_settings', 'vlm_safety_scan_interval')
    op.drop_column('user_settings', 'vlm_safety_scan_enabled')
