"""Add user permissions table for RBAC

Revision ID: 006_add_user_permissions
Revises: 005_add_multi_llm_provider_support
Create Date: 2025-12-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON


# revision identifiers
revision = '006_add_user_permissions'
down_revision = '005_add_multi_llm_provider_support'
branch_labels = None
depends_on = None


def upgrade():
    # Create user_permissions table
    op.create_table(
        'user_permissions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        
        # Page Access
        sa.Column('can_access_dashboard', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('can_access_cameras', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('can_access_events', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('can_access_monitor', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('can_access_assistant', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('can_access_settings', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('can_access_admin', sa.Boolean(), nullable=False, server_default='false'),
        
        # Camera Permissions
        sa.Column('can_view_cameras', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('can_add_cameras', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('can_edit_cameras', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('can_delete_cameras', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('can_control_ptz', sa.Boolean(), nullable=False, server_default='false'),
        
        # Event Permissions
        sa.Column('can_view_events', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('can_acknowledge_events', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('can_delete_events', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('can_export_events', sa.Boolean(), nullable=False, server_default='true'),
        
        # Settings Permissions
        sa.Column('can_modify_detection_settings', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('can_modify_vlm_settings', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('can_modify_notification_settings', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('can_modify_system_settings', sa.Boolean(), nullable=False, server_default='false'),
        
        # User Management
        sa.Column('can_view_users', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('can_add_users', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('can_edit_users', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('can_delete_users', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('can_change_user_roles', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('can_change_user_permissions', sa.Boolean(), nullable=False, server_default='false'),
        
        # System Permissions
        sa.Column('can_restart_services', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('can_view_system_logs', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('can_manage_models', sa.Boolean(), nullable=False, server_default='false'),
        
        # Camera Access Control
        sa.Column('allowed_camera_ids', JSON, nullable=True),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('user_id')
    )
    
    op.create_index('ix_user_permissions_user_id', 'user_permissions', ['user_id'])
    
    # Create permissions for existing users
    # Admin users get full access
    op.execute("""
        INSERT INTO user_permissions (
            user_id,
            can_access_dashboard, can_access_cameras, can_access_events, can_access_monitor,
            can_access_assistant, can_access_settings, can_access_admin,
            can_view_cameras, can_add_cameras, can_edit_cameras, can_delete_cameras, can_control_ptz,
            can_view_events, can_acknowledge_events, can_delete_events, can_export_events,
            can_modify_detection_settings, can_modify_vlm_settings, can_modify_notification_settings, can_modify_system_settings,
            can_view_users, can_add_users, can_edit_users, can_delete_users, can_change_user_roles, can_change_user_permissions,
            can_restart_services, can_view_system_logs, can_manage_models
        )
        SELECT 
            id,
            true, true, true, true,
            true, true, true,
            true, true, true, true, true,
            true, true, true, true,
            true, true, true, true,
            true, true, true, true, true, true,
            true, true, true
        FROM users
        WHERE role = 'admin'
        ON CONFLICT (user_id) DO NOTHING
    """)
    
    # Operator users get moderate access
    op.execute("""
        INSERT INTO user_permissions (
            user_id,
            can_access_dashboard, can_access_cameras, can_access_events, can_access_monitor,
            can_access_assistant, can_access_settings, can_access_admin,
            can_view_cameras, can_add_cameras, can_edit_cameras, can_delete_cameras, can_control_ptz,
            can_view_events, can_acknowledge_events, can_delete_events, can_export_events,
            can_modify_detection_settings, can_modify_vlm_settings, can_modify_notification_settings, can_modify_system_settings,
            can_view_users, can_add_users, can_edit_users, can_delete_users, can_change_user_roles, can_change_user_permissions,
            can_restart_services, can_view_system_logs, can_manage_models
        )
        SELECT 
            id,
            true, true, true, true,
            true, true, false,
            true, true, true, false, true,
            true, true, false, true,
            true, false, true, false,
            false, false, false, false, false, false,
            false, false, false
        FROM users
        WHERE role = 'operator'
        ON CONFLICT (user_id) DO NOTHING
    """)
    
    # Viewer users get read-only access
    op.execute("""
        INSERT INTO user_permissions (
            user_id,
            can_access_dashboard, can_access_cameras, can_access_events, can_access_monitor,
            can_access_assistant, can_access_settings, can_access_admin,
            can_view_cameras, can_add_cameras, can_edit_cameras, can_delete_cameras, can_control_ptz,
            can_view_events, can_acknowledge_events, can_delete_events, can_export_events,
            can_modify_detection_settings, can_modify_vlm_settings, can_modify_notification_settings, can_modify_system_settings,
            can_view_users, can_add_users, can_edit_users, can_delete_users, can_change_user_roles, can_change_user_permissions,
            can_restart_services, can_view_system_logs, can_manage_models
        )
        SELECT 
            id,
            true, true, true, true,
            true, false, false,
            true, false, false, false, false,
            true, false, false, true,
            false, false, false, false,
            false, false, false, false, false, false,
            false, false, false
        FROM users
        WHERE role = 'viewer'
        ON CONFLICT (user_id) DO NOTHING
    """)


def downgrade():
    op.drop_index('ix_user_permissions_user_id', 'user_permissions')
    op.drop_table('user_permissions')
