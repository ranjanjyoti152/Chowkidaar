"""
Chowkidaar NVR - Authentication Routes
"""
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, func

from app.core.database import get_db
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    verify_token
)
from app.models.user import User, UserRole
from app.models.permission import UserPermission, get_default_permissions_for_role
from app.schemas.auth import Token, LoginRequest, RefreshTokenRequest, RegisterRequest
from app.schemas.user import UserResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """Authenticate user and return tokens"""
    # Find user by username or email
    result = await db.execute(
        select(User).where(
            or_(
                User.username == form_data.username,
                User.email == form_data.username
            )
        )
    )
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled"
        )
    
    # Check if user is approved (superusers and first admin are auto-approved)
    if not user.is_approved:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is pending approval. Please wait for admin to approve your registration."
        )
    
    # Update last login
    user.last_login = datetime.utcnow()
    await db.commit()
    
    # Create tokens
    access_token = create_access_token(
        subject=user.id,
        additional_claims={"role": user.role.value}
    )
    refresh_token = create_refresh_token(subject=user.id)
    
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer"
    )


@router.post("/register", response_model=UserResponse)
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db)
):
    """Register a new user"""
    # Check if email exists
    result = await db.execute(
        select(User).where(User.email == request.email)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Check if username exists
    result = await db.execute(
        select(User).where(User.username == request.username)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken"
        )
    
    # Check if this is the first user (will be admin)
    user_count_result = await db.execute(select(func.count(User.id)))
    user_count = user_count_result.scalar() or 0
    is_first_user = user_count == 0
    
    # First user is always admin, subsequent users are viewers by default
    user_role = UserRole.admin if is_first_user else UserRole.viewer
    
    # Create user
    user = User(
        email=request.email,
        username=request.username,
        hashed_password=get_password_hash(request.password),
        full_name=request.full_name,
        role=user_role,
        is_superuser=is_first_user,  # Only first user is superuser
        is_approved=is_first_user,   # First user is auto-approved, others need admin approval
        approved_at=datetime.utcnow() if is_first_user else None
    )
    
    db.add(user)
    await db.flush()  # Get user ID
    
    # Create default permissions based on role
    default_perms = get_default_permissions_for_role(user_role.value)
    permissions = UserPermission(
        user_id=user.id,
        **default_perms
    )
    db.add(permissions)
    
    await db.commit()
    await db.refresh(user)
    
    return user


@router.post("/refresh", response_model=Token)
async def refresh_token(
    request: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db)
):
    """Refresh access token"""
    user_id = verify_token(request.refresh_token, "refresh")
    
    # Get user
    result = await db.execute(
        select(User).where(User.id == int(user_id))
    )
    user = result.scalar_one_or_none()
    
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    # Create new tokens
    access_token = create_access_token(
        subject=user.id,
        additional_claims={"role": user.role.value}
    )
    refresh_token = create_refresh_token(subject=user.id)
    
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer"
    )


@router.post("/logout")
async def logout():
    """Logout user (client should discard tokens)"""
    return {"message": "Successfully logged out"}
