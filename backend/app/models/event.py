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
    PERSON_DETECTED = "person_detected"
    VEHICLE_DETECTED = "vehicle_detected"
    FIRE_DETECTED = "fire_detected"
    SMOKE_DETECTED = "smoke_detected"
    ANIMAL_DETECTED = "animal_detected"
    MOTION_DETECTED = "motion_detected"
    INTRUSION = "intrusion"
    LOITERING = "loitering"
    CUSTOM = "custom"


class EventSeverity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Event(Base):
    __tablename__ = "events"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    
    # Event classification
    event_type: Mapped[EventType] = mapped_column(
        SQLEnum(EventType),
        nullable=False,
        index=True
    )
    severity: Mapped[EventSeverity] = mapped_column(
        SQLEnum(EventSeverity),
        default=EventSeverity.LOW,
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
