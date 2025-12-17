"""
Chowkidaar NVR - Settings Routes
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from loguru import logger

from app.core.database import get_db
from app.models.user import User
from app.models.settings import UserSettings
from app.schemas.settings import (
    SettingsResponse, SettingsUpdate, 
    DetectionSettings, VLMSettings, StorageSettings, NotificationSettings,
    TelegramSettings, EmailSettings
)
from app.api.deps import get_current_user
from app.services.vlm_service import vlm_service
from app.services.detection_service import detection_service

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
            inference_device=settings.detection_device,
            owlv2_queries=getattr(settings, 'owlv2_queries', [
                "a person", "a car", "a fire", "a lighter", "a dog", "a cat", 
                "a weapon", "a knife", "a suspicious object"
            ]) or []
        ),
        vlm=VLMSettings(
            provider=getattr(settings, 'vlm_provider', 'ollama'),
            model=settings.vlm_model,
            ollama_url=settings.vlm_url,
            openai_api_key=getattr(settings, 'openai_api_key', None),
            openai_model=getattr(settings, 'openai_model', 'gpt-4o'),
            openai_base_url=getattr(settings, 'openai_base_url', None),
            gemini_api_key=getattr(settings, 'gemini_api_key', None),
            gemini_model=getattr(settings, 'gemini_model', 'gemini-2.0-flash-exp'),
            auto_summarize=settings.auto_summarize,
            summarize_delay_seconds=settings.summarize_delay,
            safety_scan_enabled=getattr(settings, 'vlm_safety_scan_enabled', True),
            safety_scan_interval=getattr(settings, 'vlm_safety_scan_interval', 30)
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
            event_types=settings.notify_event_types or ["all"],
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
    logger.info(f"📝 Updating settings for user {current_user.id}")
    logger.debug(f"Settings update payload: {settings_update}")
    
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
        settings.owlv2_queries = settings_update.detection.owlv2_queries
    
    # Update VLM settings
    if settings_update.vlm:
        settings.vlm_provider = settings_update.vlm.provider
        settings.vlm_model = settings_update.vlm.model
        settings.vlm_url = settings_update.vlm.ollama_url
        # Handle empty strings as None for optional API keys
        settings.openai_api_key = settings_update.vlm.openai_api_key or None
        settings.openai_model = settings_update.vlm.openai_model
        settings.openai_base_url = settings_update.vlm.openai_base_url or None
        settings.gemini_api_key = settings_update.vlm.gemini_api_key or None
        settings.gemini_model = settings_update.vlm.gemini_model
        settings.auto_summarize = settings_update.vlm.auto_summarize
        settings.summarize_delay = settings_update.vlm.summarize_delay_seconds
        settings.vlm_safety_scan_enabled = settings_update.vlm.safety_scan_enabled
        settings.vlm_safety_scan_interval = settings_update.vlm.safety_scan_interval
        
        # Configure VLM service system-wide with new settings
        vlm_service.configure(
            provider=settings_update.vlm.provider,
            ollama_url=settings_update.vlm.ollama_url,
            ollama_model=settings_update.vlm.model,
            openai_api_key=settings_update.vlm.openai_api_key,
            openai_model=settings_update.vlm.openai_model,
            openai_base_url=settings_update.vlm.openai_base_url,
            gemini_api_key=settings_update.vlm.gemini_api_key,
            gemini_model=settings_update.vlm.gemini_model
        )
        logger.info(f"VLM service configured: provider={settings_update.vlm.provider}")
    
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
    
    # Invalidate detection service cache so new settings take effect immediately
    detection_service._invalidate_cache(current_user.id)
    
    logger.info(f"✅ Settings saved for user {current_user.id}: detection_model={settings.detection_model}, vlm_provider={settings.vlm_provider}, vlm_model={settings.vlm_model}")
    
    return SettingsResponse(
        detection=DetectionSettings(
            model=settings.detection_model,
            confidence_threshold=settings.detection_confidence,
            enabled_classes=settings.enabled_classes or [],
            inference_device=settings.detection_device,
            owlv2_queries=getattr(settings, 'owlv2_queries', [
                "a person", "a car", "a fire", "a lighter", "a dog", "a cat", 
                "a weapon", "a knife", "a suspicious object"
            ]) or []
        ),
        vlm=VLMSettings(
            provider=getattr(settings, 'vlm_provider', 'ollama'),
            model=settings.vlm_model,
            ollama_url=settings.vlm_url,
            openai_api_key=getattr(settings, 'openai_api_key', None),
            openai_model=getattr(settings, 'openai_model', 'gpt-4o'),
            openai_base_url=getattr(settings, 'openai_base_url', None),
            gemini_api_key=getattr(settings, 'gemini_api_key', None),
            gemini_model=getattr(settings, 'gemini_model', 'gemini-2.0-flash-exp'),
            auto_summarize=settings.auto_summarize,
            summarize_delay_seconds=settings.summarize_delay,
            safety_scan_enabled=getattr(settings, 'vlm_safety_scan_enabled', True),
            safety_scan_interval=getattr(settings, 'vlm_safety_scan_interval', 30)
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
            event_types=settings.notify_event_types or ["all"],
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
