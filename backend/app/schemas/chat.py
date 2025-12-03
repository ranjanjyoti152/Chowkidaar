"""
Chowkidaar NVR - Chat/Assistant Schemas
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel


class ChatMessageBase(BaseModel):
    content: str
    role: str = "user"


class ChatMessageCreate(ChatMessageBase):
    event_id: Optional[int] = None
    message_metadata: Dict[str, Any] = {}


class ChatMessageResponse(ChatMessageBase):
    id: int
    session_id: int
    event_id: Optional[int] = None
    message_metadata: Dict[str, Any] = {}
    created_at: datetime
    
    class Config:
        from_attributes = True


class ChatSessionCreate(BaseModel):
    title: Optional[str] = None
    context: Dict[str, Any] = {}


class ChatSessionResponse(BaseModel):
    id: int
    title: Optional[str] = None
    user_id: int
    context: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    messages: List[ChatMessageResponse] = []
    
    class Config:
        from_attributes = True


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[int] = None
    include_events_context: bool = True
    event_ids: Optional[List[int]] = None


class RelatedEventInfo(BaseModel):
    id: int
    event_type: str
    severity: str
    timestamp: datetime
    summary: Optional[str] = None
    frame_path: Optional[str] = None
    thumbnail_path: Optional[str] = None
    camera_name: Optional[str] = None
    detected_objects: List[Dict[str, Any]] = []
    
    class Config:
        from_attributes = True


class ChatResponse(BaseModel):
    message: str
    session_id: int
    related_events: List[int] = []
    events_with_images: List[RelatedEventInfo] = []
    metadata: Dict[str, Any] = {}


class AssistantQuery(BaseModel):
    query: str
    filters: Optional[Dict[str, Any]] = None
    limit: int = 10
