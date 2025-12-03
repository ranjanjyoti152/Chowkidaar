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
    DetectionSettings, VLMSettings, StorageSettings, NotificationSettings,
    TelegramSettings, EmailSettings
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
            min_severity=settings.min_severity,
            event_types=settings.notify_event_types or ["intrusion", "theft_attempt", "suspicious", "fire_detected", "smoke_detected"],
            telegram=TelegramSettings(
                enabled=settings.telegram_enabled,
                bot_token=settings.telegram_bot_token,
                chat_id=settings.telegram_chat_id,
                send_photo=settings.telegram_send_photo,
                send_summary=settings.telegram_send_summary,
                send_details=settings.telegram_send_details
            ),
            email=EmailSettings(
                enabled=settings.email_enabled,
                smtp_host=settings.email_smtp_host,
                smtp_port=settings.email_smtp_port,
                smtp_user=settings.email_smtp_user,
                smtp_password=settings.email_smtp_password,
                from_address=settings.email_from_address,
                recipients=settings.email_recipients or [],
                send_photo=settings.email_send_photo,
                send_summary=settings.email_send_summary,
                send_details=settings.email_send_details
            )
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
        notif = settings_update.notifications
        settings.notifications_enabled = notif.enabled
        settings.min_severity = notif.min_severity
        settings.notify_event_types = notif.event_types
        
        # Telegram settings
        if notif.telegram:
            settings.telegram_enabled = notif.telegram.enabled
            settings.telegram_bot_token = notif.telegram.bot_token
            settings.telegram_chat_id = notif.telegram.chat_id
            settings.telegram_send_photo = notif.telegram.send_photo
            settings.telegram_send_summary = notif.telegram.send_summary
            settings.telegram_send_details = notif.telegram.send_details
        
        # Email settings
        if notif.email:
            settings.email_enabled = notif.email.enabled
            settings.email_smtp_host = notif.email.smtp_host
            settings.email_smtp_port = notif.email.smtp_port
            settings.email_smtp_user = notif.email.smtp_user
            settings.email_smtp_password = notif.email.smtp_password
            settings.email_from_address = notif.email.from_address
            settings.email_recipients = notif.email.recipients
            settings.email_send_photo = notif.email.send_photo
            settings.email_send_summary = notif.email.send_summary
            settings.email_send_details = notif.email.send_details
    
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
            min_severity=settings.min_severity,
            event_types=settings.notify_event_types or ["intrusion", "theft_attempt", "suspicious", "fire_detected", "smoke_detected"],
            telegram=TelegramSettings(
                enabled=settings.telegram_enabled,
                bot_token=settings.telegram_bot_token,
                chat_id=settings.telegram_chat_id,
                send_photo=settings.telegram_send_photo,
                send_summary=settings.telegram_send_summary,
                send_details=settings.telegram_send_details
            ),
            email=EmailSettings(
                enabled=settings.email_enabled,
                smtp_host=settings.email_smtp_host,
                smtp_port=settings.email_smtp_port,
                smtp_user=settings.email_smtp_user,
                smtp_password=settings.email_smtp_password,
                from_address=settings.email_from_address,
                recipients=settings.email_recipients or [],
                send_photo=settings.email_send_photo,
                send_summary=settings.email_send_summary,
                send_details=settings.email_send_details
            )
        ),
        updated_at=settings.updated_at
    )
