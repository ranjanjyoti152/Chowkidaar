"""
Chowkidaar NVR - User Schemas
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator
from app.models.user import UserRole


class UserBase(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=100)
    full_name: Optional[str] = None


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)
    role: UserRole = UserRole.viewer
    
    @field_validator('role', mode='before')
    @classmethod
    def normalize_role(cls, v):
        if isinstance(v, str):
            return v.lower()
        return v


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = Field(None, min_length=3, max_length=100)
    full_name: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    
    @field_validator('role', mode='before')
    @classmethod
    def normalize_role(cls, v):
        if isinstance(v, str):
            return v.lower()
        return v


class UserPasswordUpdate(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)


class UserResponse(UserBase):
    id: int
    role: UserRole
    is_active: bool
    is_superuser: bool
    is_approved: bool = False
    approved_at: Optional[datetime] = None
    created_at: datetime
    last_login: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class UserWithStats(UserResponse):
    cameras_count: int = 0
    events_count: int = 0
