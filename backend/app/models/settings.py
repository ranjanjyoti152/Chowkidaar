"""
Chowkidaar NVR - User Settings Model
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, Integer, ForeignKey, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class UserSettings(Base):
    """Store user-specific settings"""
    __tablename__ = "user_settings"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    
    # User association
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # One settings record per user
        index=True
    )
    
    # Detection settings
    detection_model: Mapped[str] = mapped_column(String(100), default="yolov8n")
    detection_confidence: Mapped[float] = mapped_column(default=0.5)
    detection_device: Mapped[str] = mapped_column(String(50), default="cuda")
    enabled_classes: Mapped[list] = mapped_column(JSON, default=list)
    
    # VLM settings
    vlm_model: Mapped[str] = mapped_column(String(100), default="gemma3:4b")
    vlm_url: Mapped[str] = mapped_column(String(255), default="http://localhost:11434")
    auto_summarize: Mapped[bool] = mapped_column(default=True)
    summarize_delay: Mapped[int] = mapped_column(default=5)
    
    # Storage settings
    recordings_path: Mapped[str] = mapped_column(String(500), default="/data/recordings")
    snapshots_path: Mapped[str] = mapped_column(String(500), default="/data/snapshots")
    max_storage_gb: Mapped[int] = mapped_column(default=500)
    retention_days: Mapped[int] = mapped_column(default=30)
    
    # Notification settings
    notifications_enabled: Mapped[bool] = mapped_column(default=True)
    email_enabled: Mapped[bool] = mapped_column(default=False)
    email_recipients: Mapped[list] = mapped_column(JSON, default=list)
    min_severity: Mapped[str] = mapped_column(String(20), default="high")
    
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
    user: Mapped["User"] = relationship("User", back_populates="settings")
    
    def __repr__(self) -> str:
        return f"<UserSettings(user_id={self.user_id})>"
