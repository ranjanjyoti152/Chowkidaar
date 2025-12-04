"""
Chowkidaar NVR - Camera Schemas
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator
from app.models.camera import CameraStatus, CameraType


class CameraBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    stream_url: str
    camera_type: CameraType = CameraType.rtsp
    location: Optional[str] = None
    
    # Context-aware detection settings
    location_type: Optional[str] = None  # office, kitchen, warehouse, entrance, parking, bedroom, etc.
    expected_activity: Optional[str] = None  # "people working on computers", "cooking with fire"
    unexpected_activity: Optional[str] = None  # "running", "fighting", "strangers at night"
    normal_conditions: Optional[str] = None  # "5-10 people during work hours", "fire on stove is normal"
    
    @field_validator('camera_type', mode='before')
    @classmethod
    def normalize_camera_type(cls, v):
        if isinstance(v, str):
            return v.lower()
        return v


class CameraCreate(CameraBase):
    username: Optional[str] = None
    password: Optional[str] = None
    is_enabled: bool = True
    detection_enabled: bool = True
    recording_enabled: bool = False
    fps: int = Field(default=15, ge=1, le=60)


class CameraUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    stream_url: Optional[str] = None
    camera_type: Optional[CameraType] = None
    username: Optional[str] = None
    password: Optional[str] = None
    location: Optional[str] = None
    location_type: Optional[str] = None
    expected_activity: Optional[str] = None
    unexpected_activity: Optional[str] = None
    normal_conditions: Optional[str] = None
    is_enabled: Optional[bool] = None
    detection_enabled: Optional[bool] = None
    recording_enabled: Optional[bool] = None
    fps: Optional[int] = Field(None, ge=1, le=60)
    
    @field_validator('camera_type', mode='before')
    @classmethod
    def normalize_camera_type(cls, v):
        if isinstance(v, str):
            return v.lower()
        return v


class CameraResponse(CameraBase):
    id: int
    status: CameraStatus
    is_enabled: bool
    detection_enabled: bool
    recording_enabled: bool
    fps: int
    resolution_width: Optional[int] = None
    resolution_height: Optional[int] = None
    last_seen: Optional[datetime] = None
    error_message: Optional[str] = None
    location_type: Optional[str] = None
    expected_activity: Optional[str] = None
    unexpected_activity: Optional[str] = None
    normal_conditions: Optional[str] = None
    owner_id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class CameraWithStats(CameraResponse):
    events_today: int = 0
    events_total: int = 0
    uptime_percentage: float = 0.0


class CameraStatusUpdate(BaseModel):
    status: CameraStatus
    error_message: Optional[str] = None


class CameraTestResult(BaseModel):
    success: bool
    message: str
    resolution: Optional[str] = None
    fps: Optional[int] = None
