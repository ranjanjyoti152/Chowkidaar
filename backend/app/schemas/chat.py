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
    metadata: Dict[str, Any] = {}


class ChatMessageResponse(ChatMessageBase):
    id: int
    session_id: int
    event_id: Optional[int] = None
    metadata: Dict[str, Any]
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


class ChatResponse(BaseModel):
    message: str
    session_id: int
    related_events: List[int] = []
    metadata: Dict[str, Any] = {}


class AssistantQuery(BaseModel):
    query: str
    filters: Optional[Dict[str, Any]] = None
    limit: int = 10
