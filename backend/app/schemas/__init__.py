"""
Chowkidaar NVR - Schemas Module
"""
from app.schemas.user import (
    UserBase, UserCreate, UserUpdate, UserPasswordUpdate, UserResponse, UserWithStats
)
from app.schemas.auth import (
    Token, TokenPayload, LoginRequest, RefreshTokenRequest, RegisterRequest
)
from app.schemas.camera import (
    CameraBase, CameraCreate, CameraUpdate, CameraResponse, CameraWithStats,
    CameraStatusUpdate, CameraTestResult
)
from app.schemas.event import (
    DetectedObject, EventBase, EventCreate, EventUpdate, EventResponse,
    EventWithCamera, EventFilter, EventStats, EventSummaryRequest
)
from app.schemas.chat import (
    ChatMessageBase, ChatMessageCreate, ChatMessageResponse,
    ChatSessionCreate, ChatSessionResponse, ChatRequest, ChatResponse, AssistantQuery
)
from app.schemas.system import (
    CPUStats, MemoryStats, DiskStats, GPUStats, NetworkStats,
    ProcessStats, InferenceStats, SystemStats, SystemHealth
)

__all__ = [
    # User
    "UserBase", "UserCreate", "UserUpdate", "UserPasswordUpdate", "UserResponse", "UserWithStats",
    # Auth
    "Token", "TokenPayload", "LoginRequest", "RefreshTokenRequest", "RegisterRequest",
    # Camera
    "CameraBase", "CameraCreate", "CameraUpdate", "CameraResponse", "CameraWithStats",
    "CameraStatusUpdate", "CameraTestResult",
    # Event
    "DetectedObject", "EventBase", "EventCreate", "EventUpdate", "EventResponse",
    "EventWithCamera", "EventFilter", "EventStats", "EventSummaryRequest",
    # Chat
    "ChatMessageBase", "ChatMessageCreate", "ChatMessageResponse",
    "ChatSessionCreate", "ChatSessionResponse", "ChatRequest", "ChatResponse", "AssistantQuery",
    # System
    "CPUStats", "MemoryStats", "DiskStats", "GPUStats", "NetworkStats",
    "ProcessStats", "InferenceStats", "SystemStats", "SystemHealth"
]
