"""
Chowkidaar NVR - Permission Model
Granular permissions for Role-Based Access Control
"""
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Boolean, DateTime, Integer, ForeignKey, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class UserPermission(Base):
    """
    Stores granular permissions for each user.
    Admin can customize what each user can access/modify.
    """
    __tablename__ = "user_permissions"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("users.id", ondelete="CASCADE"), 
        unique=True,
        nullable=False
    )
    
    # Page Access Permissions
    can_access_dashboard: Mapped[bool] = mapped_column(Boolean, default=True)
    can_access_cameras: Mapped[bool] = mapped_column(Boolean, default=True)
    can_access_events: Mapped[bool] = mapped_column(Boolean, default=True)
    can_access_monitor: Mapped[bool] = mapped_column(Boolean, default=True)
    can_access_assistant: Mapped[bool] = mapped_column(Boolean, default=True)
    can_access_settings: Mapped[bool] = mapped_column(Boolean, default=False)
    can_access_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Camera Permissions
    can_view_cameras: Mapped[bool] = mapped_column(Boolean, default=True)
    can_add_cameras: Mapped[bool] = mapped_column(Boolean, default=False)
    can_edit_cameras: Mapped[bool] = mapped_column(Boolean, default=False)
    can_delete_cameras: Mapped[bool] = mapped_column(Boolean, default=False)
    can_control_ptz: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Event Permissions
    can_view_events: Mapped[bool] = mapped_column(Boolean, default=True)
    can_acknowledge_events: Mapped[bool] = mapped_column(Boolean, default=False)
    can_delete_events: Mapped[bool] = mapped_column(Boolean, default=False)
    can_export_events: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Settings Permissions
    can_modify_detection_settings: Mapped[bool] = mapped_column(Boolean, default=False)
    can_modify_vlm_settings: Mapped[bool] = mapped_column(Boolean, default=False)
    can_modify_notification_settings: Mapped[bool] = mapped_column(Boolean, default=False)
    can_modify_system_settings: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # User Management Permissions
    can_view_users: Mapped[bool] = mapped_column(Boolean, default=False)
    can_add_users: Mapped[bool] = mapped_column(Boolean, default=False)
    can_edit_users: Mapped[bool] = mapped_column(Boolean, default=False)
    can_delete_users: Mapped[bool] = mapped_column(Boolean, default=False)
    can_change_user_roles: Mapped[bool] = mapped_column(Boolean, default=False)
    can_change_user_permissions: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # System Permissions
    can_restart_services: Mapped[bool] = mapped_column(Boolean, default=False)
    can_view_system_logs: Mapped[bool] = mapped_column(Boolean, default=False)
    can_manage_models: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Specific camera access (JSON array of camera IDs, null = all cameras)
    allowed_camera_ids: Mapped[Optional[List[int]]] = mapped_column(JSON, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )
    
    # Relationship
    user: Mapped["User"] = relationship("User", back_populates="permissions")
    
    def __repr__(self) -> str:
        return f"<UserPermission(user_id={self.user_id})>"


# Default permission templates based on role
ROLE_PERMISSION_TEMPLATES = {
    "admin": {
        # Full access to everything
        "can_access_dashboard": True,
        "can_access_cameras": True,
        "can_access_events": True,
        "can_access_monitor": True,
        "can_access_assistant": True,
        "can_access_settings": True,
        "can_access_admin": True,
        "can_view_cameras": True,
        "can_add_cameras": True,
        "can_edit_cameras": True,
        "can_delete_cameras": True,
        "can_control_ptz": True,
        "can_view_events": True,
        "can_acknowledge_events": True,
        "can_delete_events": True,
        "can_export_events": True,
        "can_modify_detection_settings": True,
        "can_modify_vlm_settings": True,
        "can_modify_notification_settings": True,
        "can_modify_system_settings": True,
        "can_view_users": True,
        "can_add_users": True,
        "can_edit_users": True,
        "can_delete_users": True,
        "can_change_user_roles": True,
        "can_change_user_permissions": True,
        "can_restart_services": True,
        "can_view_system_logs": True,
        "can_manage_models": True,
        "allowed_camera_ids": None,  # All cameras
    },
    "operator": {
        # Can manage cameras and events, limited settings
        "can_access_dashboard": True,
        "can_access_cameras": True,
        "can_access_events": True,
        "can_access_monitor": True,
        "can_access_assistant": True,
        "can_access_settings": True,
        "can_access_admin": False,
        "can_view_cameras": True,
        "can_add_cameras": True,
        "can_edit_cameras": True,
        "can_delete_cameras": False,
        "can_control_ptz": True,
        "can_view_events": True,
        "can_acknowledge_events": True,
        "can_delete_events": False,
        "can_export_events": True,
        "can_modify_detection_settings": True,
        "can_modify_vlm_settings": False,
        "can_modify_notification_settings": True,
        "can_modify_system_settings": False,
        "can_view_users": False,
        "can_add_users": False,
        "can_edit_users": False,
        "can_delete_users": False,
        "can_change_user_roles": False,
        "can_change_user_permissions": False,
        "can_restart_services": False,
        "can_view_system_logs": False,
        "can_manage_models": False,
        "allowed_camera_ids": None,  # All cameras
    },
    "viewer": {
        # Read-only access
        "can_access_dashboard": True,
        "can_access_cameras": True,
        "can_access_events": True,
        "can_access_monitor": True,
        "can_access_assistant": True,
        "can_access_settings": False,
        "can_access_admin": False,
        "can_view_cameras": True,
        "can_add_cameras": False,
        "can_edit_cameras": False,
        "can_delete_cameras": False,
        "can_control_ptz": False,
        "can_view_events": True,
        "can_acknowledge_events": False,
        "can_delete_events": False,
        "can_export_events": True,
        "can_modify_detection_settings": False,
        "can_modify_vlm_settings": False,
        "can_modify_notification_settings": False,
        "can_modify_system_settings": False,
        "can_view_users": False,
        "can_add_users": False,
        "can_edit_users": False,
        "can_delete_users": False,
        "can_change_user_roles": False,
        "can_change_user_permissions": False,
        "can_restart_services": False,
        "can_view_system_logs": False,
        "can_manage_models": False,
        "allowed_camera_ids": None,  # All cameras (can be restricted by admin)
    }
}


def get_default_permissions_for_role(role: str) -> dict:
    """Get default permission values for a given role"""
    return ROLE_PERMISSION_TEMPLATES.get(role, ROLE_PERMISSION_TEMPLATES["viewer"])
