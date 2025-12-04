"""
Chowkidaar NVR - API Dependencies
"""
from typing import Optional, Generator, Callable
from functools import wraps
from fastapi import Depends, HTTPException, status, Query, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import verify_token
from app.models.user import User, UserRole
from app.models.permission import UserPermission


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_token_from_header_or_query(
    request: Request,
    token_header: Optional[str] = Depends(oauth2_scheme),
    token_query: Optional[str] = Query(None, alias="token")
) -> str:
    """Get token from header or query parameter"""
    token = token_header or token_query
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    token: str = Depends(get_token_from_header_or_query)
) -> User:
    """Get the current authenticated user with permissions loaded"""
    user_id = verify_token(token, "access")
    
    result = await db.execute(
        select(User)
        .options(selectinload(User.permissions))
        .where(User.id == int(user_id))
    )
    user = result.scalar_one_or_none()
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled"
        )
    
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get current active user"""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    return current_user


async def get_current_superuser(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get current superuser"""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    return current_user


def require_roles(*roles: UserRole):
    """Dependency factory for role-based access"""
    async def role_checker(
        current_user: User = Depends(get_current_user)
    ) -> User:
        if current_user.role not in roles and not current_user.is_superuser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required roles: {[r.value for r in roles]}"
            )
        return current_user
    return role_checker


# Common role dependencies
require_admin = require_roles(UserRole.admin)
require_operator = require_roles(UserRole.admin, UserRole.operator)
require_viewer = require_roles(UserRole.admin, UserRole.operator, UserRole.viewer)


# ===========================================
# Permission-Based Access Control Dependencies
# ===========================================

def check_permission(permission_attr: str, error_msg: str = "You don't have permission to access this resource"):
    """
    Dependency factory for permission-based access control.
    Checks if user has a specific permission or is superuser.
    
    Usage:
        @router.get("/events", dependencies=[Depends(check_permission("can_view_events"))])
    """
    async def permission_checker(
        current_user: User = Depends(get_current_user)
    ) -> User:
        # Superusers bypass all permission checks
        if current_user.is_superuser:
            return current_user
        
        # Check if user has permission record
        if not current_user.permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=error_msg
            )
        
        # Check the specific permission
        if not getattr(current_user.permissions, permission_attr, False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=error_msg
            )
        
        return current_user
    return permission_checker


def check_camera_access(camera_id: int):
    """
    Check if user has access to a specific camera.
    Returns dependency that checks camera access.
    """
    async def camera_checker(
        current_user: User = Depends(get_current_user)
    ) -> User:
        # Superusers have access to all cameras
        if current_user.is_superuser:
            return current_user
        
        # If no permission record or allowed_camera_ids is None, user has access to all cameras
        if not current_user.permissions or current_user.permissions.allowed_camera_ids is None:
            return current_user
        
        # Check if camera_id is in allowed list
        if camera_id not in current_user.permissions.allowed_camera_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this camera"
            )
        
        return current_user
    return camera_checker


async def get_user_allowed_camera_ids(
    current_user: User = Depends(get_current_user)
) -> Optional[list]:
    """
    Get the list of camera IDs the user is allowed to access.
    Returns None if user has access to all cameras.
    """
    # Superusers have access to all cameras
    if current_user.is_superuser:
        return None
    
    # If no permission record or allowed_camera_ids is None, user has access to all
    if not current_user.permissions or current_user.permissions.allowed_camera_ids is None:
        return None
    
    return current_user.permissions.allowed_camera_ids


# Permission dependency shortcuts
require_dashboard_view = check_permission("can_view_dashboard", "You don't have permission to view the dashboard")
require_events_view = check_permission("can_view_events", "You don't have permission to view events")
require_events_manage = check_permission("can_manage_events", "You don't have permission to manage events")
require_cameras_view = check_permission("can_view_cameras", "You don't have permission to view cameras")
require_cameras_add = check_permission("can_add_cameras", "You don't have permission to add cameras")
require_cameras_edit = check_permission("can_edit_cameras", "You don't have permission to edit cameras")
require_cameras_delete = check_permission("can_delete_cameras", "You don't have permission to delete cameras")
require_monitor_view = check_permission("can_view_monitor", "You don't have permission to view the monitor")
require_settings_view = check_permission("can_view_settings", "You don't have permission to view settings")
require_settings_manage = check_permission("can_manage_settings", "You don't have permission to manage settings")
require_users_view = check_permission("can_view_users", "You don't have permission to view users")
require_users_manage = check_permission("can_manage_users", "You don't have permission to manage users")
require_assistant_view = check_permission("can_view_assistant", "You don't have permission to access the assistant")
