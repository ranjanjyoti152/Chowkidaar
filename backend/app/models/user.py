"""
Chowkidaar NVR - User Model
"""
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Boolean, DateTime, Enum as SQLEnum, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum
from app.core.database import Base


class UserRole(str, enum.Enum):
    """Case-insensitive user role enum"""
    admin = "admin"
    operator = "operator"
    viewer = "viewer"
    
    @classmethod
    def _missing_(cls, value):
        """Handle case-insensitive lookup"""
        if isinstance(value, str):
            lower_value = value.lower()
            for member in cls:
                if member.value == lower_value:
                    return member
        return None
    
    def __str__(self):
        return self.value


class User(Base):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    role: Mapped[UserRole] = mapped_column(
        SQLEnum(UserRole, name='user_role', create_type=False, native_enum=True),
        default=UserRole.viewer,
        nullable=False
    )
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Approval system - new users need admin approval
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    approved_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
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
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Relationships
    cameras: Mapped[List["Camera"]] = relationship(
        "Camera",
        back_populates="owner",
        lazy="selectin"
    )
    events: Mapped[List["Event"]] = relationship(
        "Event",
        back_populates="user",
        lazy="selectin"
    )
    chat_sessions: Mapped[List["ChatSession"]] = relationship(
        "ChatSession",
        back_populates="user",
        lazy="selectin"
    )
    settings: Mapped[Optional["UserSettings"]] = relationship(
        "UserSettings",
        back_populates="user",
        uselist=False,
        lazy="selectin",
        cascade="all, delete-orphan"
    )
    permissions: Mapped[Optional["UserPermission"]] = relationship(
        "UserPermission",
        back_populates="user",
        uselist=False,
        lazy="selectin",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}', role='{self.role}')>"
