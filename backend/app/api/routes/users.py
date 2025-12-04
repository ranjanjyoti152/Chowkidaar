"""
Chowkidaar NVR - User Management Routes
"""
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel

from app.core.database import get_db
from app.core.security import get_password_hash, verify_password
from app.models.user import User, UserRole
from app.models.camera import Camera
from app.models.event import Event
from app.models.permission import UserPermission, get_default_permissions_for_role
from app.schemas.user import (
    UserCreate, UserUpdate, UserResponse, UserWithStats, UserPasswordUpdate
)
from app.api.deps import get_current_user, get_current_superuser, require_admin

router = APIRouter(prefix="/users", tags=["Users"])


# Permission schemas
class PermissionUpdateRequest(BaseModel):
    """Request to update user permissions"""
    # Page Access
    can_access_dashboard: Optional[bool] = None
    can_access_cameras: Optional[bool] = None
    can_access_events: Optional[bool] = None
    can_access_monitor: Optional[bool] = None
    can_access_assistant: Optional[bool] = None
    can_access_settings: Optional[bool] = None
    can_access_admin: Optional[bool] = None
    
    # Camera Permissions
    can_view_cameras: Optional[bool] = None
    can_add_cameras: Optional[bool] = None
    can_edit_cameras: Optional[bool] = None
    can_delete_cameras: Optional[bool] = None
    can_control_ptz: Optional[bool] = None
    
    # Event Permissions
    can_view_events: Optional[bool] = None
    can_acknowledge_events: Optional[bool] = None
    can_delete_events: Optional[bool] = None
    can_export_events: Optional[bool] = None
    
    # Settings Permissions
    can_modify_detection_settings: Optional[bool] = None
    can_modify_vlm_settings: Optional[bool] = None
    can_modify_notification_settings: Optional[bool] = None
    can_modify_system_settings: Optional[bool] = None
    
    # User Management
    can_view_users: Optional[bool] = None
    can_add_users: Optional[bool] = None
    can_edit_users: Optional[bool] = None
    can_delete_users: Optional[bool] = None
    can_change_user_roles: Optional[bool] = None
    can_change_user_permissions: Optional[bool] = None
    
    # System
    can_restart_services: Optional[bool] = None
    can_view_system_logs: Optional[bool] = None
    can_manage_models: Optional[bool] = None
    
    # Camera Access
    allowed_camera_ids: Optional[List[int]] = None


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """Get current user information"""
    return current_user


@router.put("/me", response_model=UserResponse)
async def update_current_user(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update current user information"""
    # Check email uniqueness
    if user_update.email and user_update.email != current_user.email:
        result = await db.execute(
            select(User).where(User.email == user_update.email)
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already in use"
            )
    
    # Check username uniqueness
    if user_update.username and user_update.username != current_user.username:
        result = await db.execute(
            select(User).where(User.username == user_update.username)
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken"
            )
    
    # Update fields
    update_data = user_update.model_dump(exclude_unset=True)
    
    # Don't allow users to change their own role
    update_data.pop("role", None)
    update_data.pop("is_active", None)
    
    for key, value in update_data.items():
        setattr(current_user, key, value)
    
    await db.commit()
    await db.refresh(current_user)
    
    return current_user


@router.put("/me/password")
async def change_password(
    password_update: UserPasswordUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Change current user password"""
    if not verify_password(password_update.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password"
        )
    
    current_user.hashed_password = get_password_hash(password_update.new_password)
    await db.commit()
    
    return {"message": "Password updated successfully"}


@router.get("", response_model=List[UserWithStats])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """List all users (admin only)"""
    result = await db.execute(
        select(User).offset(skip).limit(limit)
    )
    users = result.scalars().all()
    
    # Get stats for each user
    users_with_stats = []
    for user in users:
        # Count cameras
        cameras_result = await db.execute(
            select(func.count(Camera.id)).where(Camera.owner_id == user.id)
        )
        cameras_count = cameras_result.scalar() or 0
        
        # Count events
        events_result = await db.execute(
            select(func.count(Event.id)).where(Event.user_id == user.id)
        )
        events_count = events_result.scalar() or 0
        
        user_dict = {
            **UserResponse.model_validate(user).model_dump(),
            "cameras_count": cameras_count,
            "events_count": events_count
        }
        users_with_stats.append(UserWithStats(**user_dict))
    
    return users_with_stats


# ===========================================
# User Approval Endpoints (must be before /{user_id} routes)
# ===========================================

@router.get("/pending", response_model=List[UserResponse])
async def get_pending_users(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get all users pending approval (admin only)"""
    result = await db.execute(
        select(User).where(User.is_approved == False).order_by(User.created_at.desc())
    )
    return result.scalars().all()


@router.post("", response_model=UserResponse)
async def create_user(
    user_create: UserCreate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Create a new user (admin only)"""
    # Check if email exists
    result = await db.execute(
        select(User).where(User.email == user_create.email)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Check if username exists
    result = await db.execute(
        select(User).where(User.username == user_create.username)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken"
        )
    
    # Create user
    user = User(
        email=user_create.email,
        username=user_create.username,
        hashed_password=get_password_hash(user_create.password),
        full_name=user_create.full_name,
        role=user_create.role
    )
    
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    return user


@router.get("/{user_id}", response_model=UserWithStats)
async def get_user(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get user by ID (admin only)"""
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Get stats
    cameras_result = await db.execute(
        select(func.count(Camera.id)).where(Camera.owner_id == user.id)
    )
    cameras_count = cameras_result.scalar() or 0
    
    events_result = await db.execute(
        select(func.count(Event.id)).where(Event.user_id == user.id)
    )
    events_count = events_result.scalar() or 0
    
    return UserWithStats(
        **UserResponse.model_validate(user).model_dump(),
        cameras_count=cameras_count,
        events_count=events_count
    )


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_update: UserUpdate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update user (admin only)"""
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update fields
    update_data = user_update.model_dump(exclude_unset=True)
    
    for key, value in update_data.items():
        setattr(user, key, value)
    
    await db.commit()
    await db.refresh(user)
    
    return user


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db)
):
    """Delete user (superuser only)"""
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete yourself"
        )
    
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    await db.delete(user)
    await db.commit()
    
    return {"message": "User deleted successfully"}


# ==================== PERMISSION MANAGEMENT ====================

@router.get("/me/permissions")
async def get_my_permissions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current user's permissions"""
    result = await db.execute(
        select(UserPermission).where(UserPermission.user_id == current_user.id)
    )
    permissions = result.scalar_one_or_none()
    
    if not permissions:
        # Return default permissions based on role
        return get_default_permissions_for_role(current_user.role.value)
    
    # Return permission dict
    return {
        "can_access_dashboard": permissions.can_access_dashboard,
        "can_access_cameras": permissions.can_access_cameras,
        "can_access_events": permissions.can_access_events,
        "can_access_monitor": permissions.can_access_monitor,
        "can_access_assistant": permissions.can_access_assistant,
        "can_access_settings": permissions.can_access_settings,
        "can_access_admin": permissions.can_access_admin,
        "can_view_cameras": permissions.can_view_cameras,
        "can_add_cameras": permissions.can_add_cameras,
        "can_edit_cameras": permissions.can_edit_cameras,
        "can_delete_cameras": permissions.can_delete_cameras,
        "can_control_ptz": permissions.can_control_ptz,
        "can_view_events": permissions.can_view_events,
        "can_acknowledge_events": permissions.can_acknowledge_events,
        "can_delete_events": permissions.can_delete_events,
        "can_export_events": permissions.can_export_events,
        "can_modify_detection_settings": permissions.can_modify_detection_settings,
        "can_modify_vlm_settings": permissions.can_modify_vlm_settings,
        "can_modify_notification_settings": permissions.can_modify_notification_settings,
        "can_modify_system_settings": permissions.can_modify_system_settings,
        "can_view_users": permissions.can_view_users,
        "can_add_users": permissions.can_add_users,
        "can_edit_users": permissions.can_edit_users,
        "can_delete_users": permissions.can_delete_users,
        "can_change_user_roles": permissions.can_change_user_roles,
        "can_change_user_permissions": permissions.can_change_user_permissions,
        "can_restart_services": permissions.can_restart_services,
        "can_view_system_logs": permissions.can_view_system_logs,
        "can_manage_models": permissions.can_manage_models,
        "allowed_camera_ids": permissions.allowed_camera_ids,
    }


@router.get("/{user_id}/permissions")
async def get_user_permissions(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get user permissions (admin only)"""
    # Check user exists
    user_result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    result = await db.execute(
        select(UserPermission).where(UserPermission.user_id == user_id)
    )
    permissions = result.scalar_one_or_none()
    
    if not permissions:
        return get_default_permissions_for_role(user.role.value)
    
    return {
        "can_access_dashboard": permissions.can_access_dashboard,
        "can_access_cameras": permissions.can_access_cameras,
        "can_access_events": permissions.can_access_events,
        "can_access_monitor": permissions.can_access_monitor,
        "can_access_assistant": permissions.can_access_assistant,
        "can_access_settings": permissions.can_access_settings,
        "can_access_admin": permissions.can_access_admin,
        "can_view_cameras": permissions.can_view_cameras,
        "can_add_cameras": permissions.can_add_cameras,
        "can_edit_cameras": permissions.can_edit_cameras,
        "can_delete_cameras": permissions.can_delete_cameras,
        "can_control_ptz": permissions.can_control_ptz,
        "can_view_events": permissions.can_view_events,
        "can_acknowledge_events": permissions.can_acknowledge_events,
        "can_delete_events": permissions.can_delete_events,
        "can_export_events": permissions.can_export_events,
        "can_modify_detection_settings": permissions.can_modify_detection_settings,
        "can_modify_vlm_settings": permissions.can_modify_vlm_settings,
        "can_modify_notification_settings": permissions.can_modify_notification_settings,
        "can_modify_system_settings": permissions.can_modify_system_settings,
        "can_view_users": permissions.can_view_users,
        "can_add_users": permissions.can_add_users,
        "can_edit_users": permissions.can_edit_users,
        "can_delete_users": permissions.can_delete_users,
        "can_change_user_roles": permissions.can_change_user_roles,
        "can_change_user_permissions": permissions.can_change_user_permissions,
        "can_restart_services": permissions.can_restart_services,
        "can_view_system_logs": permissions.can_view_system_logs,
        "can_manage_models": permissions.can_manage_models,
        "allowed_camera_ids": permissions.allowed_camera_ids,
    }


@router.patch("/{user_id}/permissions")
async def update_user_permissions(
    user_id: int,
    request: PermissionUpdateRequest,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update user permissions (admin only)"""
    # Check user exists
    user_result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prevent modifying superuser if not superuser
    if user.is_superuser and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Cannot modify superuser permissions")
    
    # Get or create permissions
    result = await db.execute(
        select(UserPermission).where(UserPermission.user_id == user_id)
    )
    permissions = result.scalar_one_or_none()
    
    if not permissions:
        # Create with defaults
        default_perms = get_default_permissions_for_role(user.role.value)
        permissions = UserPermission(user_id=user_id, **default_perms)
        db.add(permissions)
        await db.flush()
    
    # Update only provided fields
    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if value is not None:
            setattr(permissions, key, value)
    
    await db.commit()
    await db.refresh(permissions)
    
    return {"message": "Permissions updated successfully"}


@router.post("/{user_id}/reset-permissions")
async def reset_user_permissions(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Reset user permissions to role defaults (admin only)"""
    # Get user
    user_result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get permissions
    result = await db.execute(
        select(UserPermission).where(UserPermission.user_id == user_id)
    )
    permissions = result.scalar_one_or_none()
    
    # Get defaults
    default_perms = get_default_permissions_for_role(user.role.value)
    
    if permissions:
        for key, value in default_perms.items():
            setattr(permissions, key, value)
    else:
        permissions = UserPermission(user_id=user_id, **default_perms)
        db.add(permissions)
    
    await db.commit()
    
    return {"message": "Permissions reset to role defaults", "role": user.role.value}


# ===========================================
# User Approval Actions
# ===========================================

@router.post("/{user_id}/approve", response_model=UserResponse)
async def approve_user(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Approve a pending user registration (admin only)"""
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.is_approved:
        raise HTTPException(status_code=400, detail="User is already approved")
    
    # Approve user
    user.is_approved = True
    user.approved_by = current_user.id
    user.approved_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(user)
    
    return user


@router.post("/{user_id}/reject")
async def reject_user(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Reject and delete a pending user registration (admin only)"""
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.is_approved:
        raise HTTPException(status_code=400, detail="Cannot reject an approved user. Use delete instead.")
    
    if user.is_superuser:
        raise HTTPException(status_code=400, detail="Cannot reject a superuser")
    
    # Delete the pending user
    await db.delete(user)
    await db.commit()
    
    return {"message": f"User {user.username} registration rejected and deleted"}


@router.post("/{user_id}/revoke-approval", response_model=UserResponse)
async def revoke_user_approval(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Revoke approval from an approved user (admin only)"""
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.is_superuser:
        raise HTTPException(status_code=400, detail="Cannot revoke approval from superuser")
    
    if not user.is_approved:
        raise HTTPException(status_code=400, detail="User is not approved")
    
    # Revoke approval
    user.is_approved = False
    user.approved_by = None
    user.approved_at = None
    
    await db.commit()
    await db.refresh(user)
    
    return user
