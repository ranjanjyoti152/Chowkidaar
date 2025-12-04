"""
Chowkidaar NVR - Camera Model
"""
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Boolean, DateTime, Integer, ForeignKey, Enum as SQLEnum, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum
from app.core.database import Base


class CameraStatus(str, enum.Enum):
    """Case-insensitive camera status enum"""
    online = "online"
    offline = "offline"
    connecting = "connecting"
    error = "error"
    disabled = "disabled"
    
    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            lower_value = value.lower()
            for member in cls:
                if member.value == lower_value:
                    return member
        return None
    
    def __str__(self):
        return self.value


class CameraType(str, enum.Enum):
    """Case-insensitive camera type enum"""
    rtsp = "rtsp"
    http = "http"
    onvif = "onvif"
    
    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            lower_value = value.lower()
            for member in cls:
                if member.value == lower_value:
                    return member
        return None
    
    def __str__(self):
        return self.value


class Camera(Base):
    __tablename__ = "cameras"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Connection settings
    stream_url: Mapped[str] = mapped_column(String(500), nullable=False)
    camera_type: Mapped[CameraType] = mapped_column(
        SQLEnum(CameraType, name='camera_type', create_type=False, native_enum=True),
        default=CameraType.rtsp,
        nullable=False
    )
    
    # Authentication (optional for some cameras)
    username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    password: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Status tracking
    status: Mapped[CameraStatus] = mapped_column(
        SQLEnum(CameraStatus, name='camera_status', create_type=False, native_enum=True),
        default=CameraStatus.offline,
        nullable=False
    )
    last_seen: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Configuration
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    detection_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    recording_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Stream settings
    fps: Mapped[int] = mapped_column(Integer, default=15)
    resolution_width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    resolution_height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Location info
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Context-aware detection settings
    # Location type helps VLM understand what's normal for this area
    location_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # office, kitchen, warehouse, entrance, parking, bedroom, etc.
    expected_activity: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # "people working on computers", "cooking with fire", "cars parking"
    unexpected_activity: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # "running", "fighting", "fire in non-kitchen area"
    normal_conditions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # "5-10 people during work hours", "fire on stove is normal", "empty at night"
    
    # Owner
    owner_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )
    
    # Relationships
    owner: Mapped["User"] = relationship("User", back_populates="cameras")
    events: Mapped[List["Event"]] = relationship(
        "Event",
        back_populates="camera",
        lazy="selectin",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<Camera(id={self.id}, name='{self.name}', status='{self.status}')>"
