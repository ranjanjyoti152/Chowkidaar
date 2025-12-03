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
    ONLINE = "online"
    OFFLINE = "offline"
    CONNECTING = "connecting"
    ERROR = "error"
    DISABLED = "disabled"


class CameraType(str, enum.Enum):
    RTSP = "rtsp"
    HTTP = "http"
    ONVIF = "onvif"


class Camera(Base):
    __tablename__ = "cameras"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Connection settings
    stream_url: Mapped[str] = mapped_column(String(500), nullable=False)
    camera_type: Mapped[CameraType] = mapped_column(
        SQLEnum(CameraType),
        default=CameraType.RTSP,
        nullable=False
    )
    
    # Authentication (optional for some cameras)
    username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    password: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Status tracking
    status: Mapped[CameraStatus] = mapped_column(
        SQLEnum(CameraStatus),
        default=CameraStatus.OFFLINE,
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
