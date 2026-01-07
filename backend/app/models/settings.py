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
    
    # V-JEPA 2 Detection settings
    vjepa2_model: Mapped[str] = mapped_column(String(100), default="vjepa2-large")
    vjepa2_buffer_size: Mapped[int] = mapped_column(default=64)  # frames in buffer
    vjepa2_sample_rate: Mapped[int] = mapped_column(default=4)   # sample every Nth frame
    detection_device: Mapped[str] = mapped_column(String(50), default="cuda")
    detection_confidence: Mapped[float] = mapped_column(default=0.5)
    
    # Legacy fields for migration compatibility (deprecated)
    detection_model: Mapped[str] = mapped_column(String(100), default="vjepa2-large")
    enabled_classes: Mapped[list] = mapped_column(JSON, default=list)
    
    # Storage settings
    recordings_path: Mapped[str] = mapped_column(String(500), default="/data/recordings")
    snapshots_path: Mapped[str] = mapped_column(String(500), default="/data/snapshots")
    max_storage_gb: Mapped[int] = mapped_column(default=500)
    retention_days: Mapped[int] = mapped_column(default=30)
    
    # Notification settings
    notifications_enabled: Mapped[bool] = mapped_column(default=True)
    min_severity: Mapped[str] = mapped_column(String(20), default="high")
    
    # Telegram settings
    telegram_enabled: Mapped[bool] = mapped_column(default=False)
    telegram_bot_token: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    telegram_chat_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    telegram_send_photo: Mapped[bool] = mapped_column(default=True)
    telegram_send_summary: Mapped[bool] = mapped_column(default=True)
    telegram_send_details: Mapped[bool] = mapped_column(default=True)
    
    # Email settings
    email_enabled: Mapped[bool] = mapped_column(default=False)
    email_smtp_host: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email_smtp_port: Mapped[int] = mapped_column(default=587)
    email_smtp_user: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email_smtp_password: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email_from_address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email_recipients: Mapped[list] = mapped_column(JSON, default=list)
    email_send_photo: Mapped[bool] = mapped_column(default=True)
    email_send_summary: Mapped[bool] = mapped_column(default=True)
    email_send_details: Mapped[bool] = mapped_column(default=True)
    
    # Event type filters for notifications
    notify_event_types: Mapped[list] = mapped_column(JSON, default=lambda: ["all"])
    
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
