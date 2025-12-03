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


class NotificationSettings(BaseModel):
    enabled: bool = True
    email_enabled: bool = False
    email_recipients: List[str] = []
    min_severity: str = "high"


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
