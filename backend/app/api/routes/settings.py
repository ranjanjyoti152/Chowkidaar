"""
Chowkidaar NVR - Settings Routes
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.user import User
from app.models.settings import UserSettings
from app.schemas.settings import (
    SettingsResponse, SettingsUpdate, 
    DetectionSettings, VLMSettings, StorageSettings, NotificationSettings
)
from app.api.deps import get_current_user

router = APIRouter(prefix="/settings", tags=["Settings"])


@router.get("", response_model=SettingsResponse)
async def get_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current user's settings"""
    result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == current_user.id)
    )
    settings = result.scalar_one_or_none()
    
    if not settings:
        # Create default settings
        settings = UserSettings(
            user_id=current_user.id,
            enabled_classes=["person", "car", "truck", "dog", "cat"]
        )
        db.add(settings)
        await db.commit()
        await db.refresh(settings)
    
    return SettingsResponse(
        detection=DetectionSettings(
            model=settings.detection_model,
            confidence_threshold=settings.detection_confidence,
            enabled_classes=settings.enabled_classes or [],
            inference_device=settings.detection_device
        ),
        vlm=VLMSettings(
            model=settings.vlm_model,
            ollama_url=settings.vlm_url,
            auto_summarize=settings.auto_summarize,
            summarize_delay_seconds=settings.summarize_delay
        ),
        storage=StorageSettings(
            recordings_path=settings.recordings_path,
            snapshots_path=settings.snapshots_path,
            max_storage_gb=settings.max_storage_gb,
            retention_days=settings.retention_days
        ),
        notifications=NotificationSettings(
            enabled=settings.notifications_enabled,
            email_enabled=settings.email_enabled,
            email_recipients=settings.email_recipients or [],
            min_severity=settings.min_severity
        ),
        updated_at=settings.updated_at
    )


@router.put("", response_model=SettingsResponse)
async def update_settings(
    settings_update: SettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update user settings"""
    result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == current_user.id)
    )
    settings = result.scalar_one_or_none()
    
    if not settings:
        settings = UserSettings(user_id=current_user.id)
        db.add(settings)
    
    # Update detection settings
    if settings_update.detection:
        settings.detection_model = settings_update.detection.model
        settings.detection_confidence = settings_update.detection.confidence_threshold
        settings.enabled_classes = settings_update.detection.enabled_classes
        settings.detection_device = settings_update.detection.inference_device
    
    # Update VLM settings
    if settings_update.vlm:
        settings.vlm_model = settings_update.vlm.model
        settings.vlm_url = settings_update.vlm.ollama_url
        settings.auto_summarize = settings_update.vlm.auto_summarize
        settings.summarize_delay = settings_update.vlm.summarize_delay_seconds
    
    # Update storage settings
    if settings_update.storage:
        settings.recordings_path = settings_update.storage.recordings_path
        settings.snapshots_path = settings_update.storage.snapshots_path
        settings.max_storage_gb = settings_update.storage.max_storage_gb
        settings.retention_days = settings_update.storage.retention_days
    
    # Update notification settings
    if settings_update.notifications:
        settings.notifications_enabled = settings_update.notifications.enabled
        settings.email_enabled = settings_update.notifications.email_enabled
        settings.email_recipients = settings_update.notifications.email_recipients
        settings.min_severity = settings_update.notifications.min_severity
    
    await db.commit()
    await db.refresh(settings)
    
    return SettingsResponse(
        detection=DetectionSettings(
            model=settings.detection_model,
            confidence_threshold=settings.detection_confidence,
            enabled_classes=settings.enabled_classes or [],
            inference_device=settings.detection_device
        ),
        vlm=VLMSettings(
            model=settings.vlm_model,
            ollama_url=settings.vlm_url,
            auto_summarize=settings.auto_summarize,
            summarize_delay_seconds=settings.summarize_delay
        ),
        storage=StorageSettings(
            recordings_path=settings.recordings_path,
            snapshots_path=settings.snapshots_path,
            max_storage_gb=settings.max_storage_gb,
            retention_days=settings.retention_days
        ),
        notifications=NotificationSettings(
            enabled=settings.notifications_enabled,
            email_enabled=settings.email_enabled,
            email_recipients=settings.email_recipients or [],
            min_severity=settings.min_severity
        ),
        updated_at=settings.updated_at
    )
