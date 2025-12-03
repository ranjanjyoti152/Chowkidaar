"""
Chowkidaar NVR - Settings Schemas
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel


class DetectionSettings(BaseModel):
    model: str = "yolov8n"
    confidence_threshold: float = 0.5
    enabled_classes: List[str] = ["person", "car", "truck", "dog", "cat"]
    inference_device: str = "cuda"


class VLMSettings(BaseModel):
    model: str = "gemma3:4b"
    ollama_url: str = "http://localhost:11434"
    auto_summarize: bool = True
    summarize_delay_seconds: int = 5


class StorageSettings(BaseModel):
    recordings_path: str = "/data/recordings"
    snapshots_path: str = "/data/snapshots"
    max_storage_gb: int = 500
    retention_days: int = 30


class TelegramSettings(BaseModel):
    enabled: bool = False
    bot_token: Optional[str] = None
    chat_id: Optional[str] = None
    send_photo: bool = True
    send_summary: bool = True
    send_details: bool = True


class EmailSettings(BaseModel):
    enabled: bool = False
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    from_address: Optional[str] = None
    recipients: List[str] = []
    send_photo: bool = True
    send_summary: bool = True
    send_details: bool = True


class NotificationSettings(BaseModel):
    enabled: bool = True
    min_severity: str = "high"
    event_types: List[str] = ["all"]
    telegram: TelegramSettings = TelegramSettings()
    email: EmailSettings = EmailSettings()


class SettingsResponse(BaseModel):
    detection: DetectionSettings
    vlm: VLMSettings
    storage: StorageSettings
    notifications: NotificationSettings
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class SettingsUpdate(BaseModel):
    detection: Optional[DetectionSettings] = None
    vlm: Optional[VLMSettings] = None
    storage: Optional[StorageSettings] = None
    notifications: Optional[NotificationSettings] = None
