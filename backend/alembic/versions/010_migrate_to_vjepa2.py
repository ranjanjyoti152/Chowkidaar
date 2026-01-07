"""
Chowkidaar NVR - Migrate to V-JEPA 2

Revision ID: 010_migrate_to_vjepa2
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = '010_migrate_to_vjepa2'
down_revision = '005_add_multi_llm_provider_support'  # Adjust based on actual last migration
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add V-JEPA 2 specific columns
    op.add_column('user_settings', 
        sa.Column('vjepa2_model', sa.String(100), server_default='vjepa2-large')
    )
    op.add_column('user_settings', 
        sa.Column('vjepa2_buffer_size', sa.Integer, server_default='64')
    )
    op.add_column('user_settings', 
        sa.Column('vjepa2_sample_rate', sa.Integer, server_default='4')
    )
    
    # Update detection_model default to vjepa2-large
    op.alter_column('user_settings', 'detection_model',
        server_default='vjepa2-large'
    )
    
    # Drop deprecated columns (VLM/LLM related)
    # Note: These are commented out for safety - run manually if needed
    # op.drop_column('user_settings', 'owlv2_queries')
    # op.drop_column('user_settings', 'vlm_provider')
    # op.drop_column('user_settings', 'vlm_model')
    # op.drop_column('user_settings', 'vlm_url')
    # op.drop_column('user_settings', 'openai_api_key')
    # op.drop_column('user_settings', 'openai_model')
    # op.drop_column('user_settings', 'openai_base_url')
    # op.drop_column('user_settings', 'gemini_api_key')
    # op.drop_column('user_settings', 'gemini_model')
    # op.drop_column('user_settings', 'auto_summarize')
    # op.drop_column('user_settings', 'summarize_delay')
    # op.drop_column('user_settings', 'vlm_safety_scan_enabled')
    # op.drop_column('user_settings', 'vlm_safety_scan_interval')


def downgrade() -> None:
    # Remove V-JEPA 2 columns
    op.drop_column('user_settings', 'vjepa2_model')
    op.drop_column('user_settings', 'vjepa2_buffer_size')
    op.drop_column('user_settings', 'vjepa2_sample_rate')
    
    # Restore detection_model default
    op.alter_column('user_settings', 'detection_model',
        server_default='yolov8n'
    )
