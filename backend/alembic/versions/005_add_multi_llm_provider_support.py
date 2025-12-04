"""Add multi LLM provider support (OpenAI, Gemini, Ollama)

Revision ID: 005
Revises: 004
Create Date: 2025-12-04

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
    # Add LLM provider selection field
    op.add_column('user_settings', sa.Column('vlm_provider', sa.String(50), server_default='ollama', nullable=False))
    
    # Add OpenAI settings
    op.add_column('user_settings', sa.Column('openai_api_key', sa.String(255), nullable=True))
    op.add_column('user_settings', sa.Column('openai_model', sa.String(100), server_default='gpt-4o', nullable=False))
    op.add_column('user_settings', sa.Column('openai_base_url', sa.String(255), nullable=True))
    
    # Add Gemini settings
    op.add_column('user_settings', sa.Column('gemini_api_key', sa.String(255), nullable=True))
    op.add_column('user_settings', sa.Column('gemini_model', sa.String(100), server_default='gemini-2.0-flash-exp', nullable=False))


def downgrade() -> None:
    op.drop_column('user_settings', 'gemini_model')
    op.drop_column('user_settings', 'gemini_api_key')
    op.drop_column('user_settings', 'openai_base_url')
    op.drop_column('user_settings', 'openai_model')
    op.drop_column('user_settings', 'openai_api_key')
    op.drop_column('user_settings', 'vlm_provider')
