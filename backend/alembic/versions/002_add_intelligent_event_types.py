"""Add intelligent event types for LLM classification

Revision ID: 002_intelligent_types
Revises: 001_initial
Create Date: 2024-12-04

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '002_intelligent_types'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add new event types for LLM-based classification"""
    # PostgreSQL doesn't allow directly modifying enums in a simple way
    # We need to add new values to the existing enum
    
    # Add new enum values to event_type
    op.execute("ALTER TYPE eventtype ADD VALUE IF NOT EXISTS 'delivery'")
    op.execute("ALTER TYPE eventtype ADD VALUE IF NOT EXISTS 'visitor'")
    op.execute("ALTER TYPE eventtype ADD VALUE IF NOT EXISTS 'package_left'")
    op.execute("ALTER TYPE eventtype ADD VALUE IF NOT EXISTS 'suspicious'")
    op.execute("ALTER TYPE eventtype ADD VALUE IF NOT EXISTS 'theft_attempt'")


def downgrade() -> None:
    """Downgrade - can't easily remove enum values in PostgreSQL"""
    # PostgreSQL doesn't support removing enum values directly
    # Events with new types would need to be updated to 'custom' type first
    pass
