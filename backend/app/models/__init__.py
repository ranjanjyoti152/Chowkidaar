"""
Chowkidaar NVR - Models Module
"""
from app.core.database import Base
from app.models.user import User, UserRole
from app.models.camera import Camera, CameraStatus, CameraType
from app.models.event import Event, EventType, EventSeverity
from app.models.chat import ChatSession, ChatMessage
from app.models.settings import UserSettings
from app.models.permission import UserPermission, ROLE_PERMISSION_TEMPLATES, get_default_permissions_for_role

__all__ = [
    "Base",
    "User",
    "UserRole",
    "Camera",
    "CameraStatus",
    "CameraType",
    "Event",
    "EventType",
    "EventSeverity",
    "ChatSession",
    "ChatMessage",
    "UserSettings",
    "UserPermission",
    "ROLE_PERMISSION_TEMPLATES",
    "get_default_permissions_for_role"
]
