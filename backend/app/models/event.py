"""
Chowkidaar NVR - Event Model
"""
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, DateTime, Integer, ForeignKey, Enum as SQLEnum, Text, Float, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum
from app.core.database import Base


class EventType(str, enum.Enum):
    """Case-insensitive event type enum"""
    person_detected = "person_detected"
    vehicle_detected = "vehicle_detected"
    fire_detected = "fire_detected"
    smoke_detected = "smoke_detected"
    animal_detected = "animal_detected"
    motion_detected = "motion_detected"
    intrusion = "intrusion"
    loitering = "loitering"
    custom = "custom"
    
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


class EventSeverity(str, enum.Enum):
    """Case-insensitive event severity enum"""
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"
    
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


class Event(Base):
    __tablename__ = "events"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    
    # Event classification
    event_type: Mapped[EventType] = mapped_column(
        SQLEnum(EventType, name='event_type', create_type=False, native_enum=True),
        nullable=False,
        index=True
    )
    severity: Mapped[EventSeverity] = mapped_column(
        SQLEnum(EventSeverity, name='event_severity', create_type=False, native_enum=True),
        default=EventSeverity.low,
        nullable=False
    )
    
    # Detection details
    detected_objects: Mapped[dict] = mapped_column(JSON, default=dict)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    
    # Frame data
    frame_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    thumbnail_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Bounding boxes and detection metadata
    detection_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    
    # VLM Summary
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    summary_generated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Timing
    timestamp: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True
    )
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Status
    is_acknowledged: Mapped[bool] = mapped_column(default=False)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    acknowledged_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Foreign keys
    camera_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("cameras.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )
    
    # Relationships
    camera: Mapped["Camera"] = relationship("Camera", back_populates="events")
    user: Mapped["User"] = relationship("User", back_populates="events")
    
    def __repr__(self) -> str:
        return f"<Event(id={self.id}, type='{self.event_type}', severity='{self.severity}')>"
