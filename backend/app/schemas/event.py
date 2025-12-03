"""
Chowkidaar NVR - Event Schemas
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator
from app.models.event import EventType, EventSeverity


class DetectedObject(BaseModel):
    class_name: str
    confidence: float
    bbox: List[float]  # [x1, y1, x2, y2]


class EventBase(BaseModel):
    event_type: EventType
    severity: EventSeverity = EventSeverity.low
    camera_id: int
    
    @field_validator('event_type', mode='before')
    @classmethod
    def normalize_event_type(cls, v):
        if isinstance(v, str):
            return v.lower()
        return v
    
    @field_validator('severity', mode='before')
    @classmethod
    def normalize_severity(cls, v):
        if isinstance(v, str):
            return v.lower()
        return v


class EventCreate(EventBase):
    detected_objects: List[Dict[str, Any]] = []
    confidence_score: float = 0.0
    detection_metadata: Dict[str, Any] = {}
    frame_path: Optional[str] = None
    thumbnail_path: Optional[str] = None


class EventUpdate(BaseModel):
    is_acknowledged: Optional[bool] = None
    notes: Optional[str] = None


class EventResponse(EventBase):
    id: int
    detected_objects: List[Dict[str, Any]]
    confidence_score: float
    frame_path: Optional[str] = None
    thumbnail_path: Optional[str] = None
    detection_metadata: Dict[str, Any]
    summary: Optional[str] = None
    summary_generated_at: Optional[datetime] = None
    timestamp: datetime
    duration_seconds: Optional[float] = None
    is_acknowledged: bool
    acknowledged_at: Optional[datetime] = None
    notes: Optional[str] = None
    user_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True


class EventWithCamera(EventResponse):
    camera_name: str
    camera_location: Optional[str] = None


class EventFilter(BaseModel):
    camera_id: Optional[int] = None
    event_type: Optional[EventType] = None
    severity: Optional[EventSeverity] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    is_acknowledged: Optional[bool] = None


class EventStats(BaseModel):
    total_events: int
    events_by_type: Dict[str, int]
    events_by_severity: Dict[str, int]
    events_by_camera: Dict[str, int]
    events_today: int
    events_this_week: int
    events_this_month: int


class EventSummaryRequest(BaseModel):
    event_id: int
    force_regenerate: bool = False
