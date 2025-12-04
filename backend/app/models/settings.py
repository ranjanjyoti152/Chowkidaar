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
    
    # VLM provider settings
    vlm_provider: Mapped[str] = mapped_column(String(50), default="ollama")  # 'ollama', 'openai', 'gemini'
    
    # Ollama settings
    vlm_model: Mapped[str] = mapped_column(String(100), default="gemma3:4b")
    vlm_url: Mapped[str] = mapped_column(String(255), default="http://localhost:11434")
    
    # OpenAI settings
    openai_api_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    openai_model: Mapped[str] = mapped_column(String(100), default="gpt-4o")
    openai_base_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Gemini settings
    gemini_api_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    gemini_model: Mapped[str] = mapped_column(String(100), default="gemini-2.0-flash-exp")
    
    # Common VLM settings
    auto_summarize: Mapped[bool] = mapped_column(default=True)
    summarize_delay: Mapped[int] = mapped_column(default=5)
    vlm_safety_scan_enabled: Mapped[bool] = mapped_column(default=True)
    vlm_safety_scan_interval: Mapped[int] = mapped_column(default=30)  # seconds between scans
    
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
