"""
Chowkidaar NVR - Camera Management Routes
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta
import cv2
import asyncio

from app.core.database import get_db
from app.models.user import User
from app.models.camera import Camera, CameraStatus
from app.models.event import Event
from app.schemas.camera import (
    CameraCreate, CameraUpdate, CameraResponse, CameraWithStats,
    CameraStatusUpdate, CameraTestResult
)
from app.api.deps import get_current_user, require_operator
from app.services.stream_handler import get_stream_manager

router = APIRouter(prefix="/cameras", tags=["Cameras"])


@router.get("", response_model=List[CameraWithStats])
async def list_cameras(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List all cameras for the current user"""
    result = await db.execute(
        select(Camera)
        .where(Camera.owner_id == current_user.id)
        .offset(skip)
        .limit(limit)
    )
    cameras = result.scalars().all()
    
    cameras_with_stats = []
    today = datetime.utcnow().date()
    
    for camera in cameras:
        # Count events today
        events_today_result = await db.execute(
            select(func.count(Event.id))
            .where(Event.camera_id == camera.id)
            .where(func.date(Event.timestamp) == today)
        )
        events_today = events_today_result.scalar() or 0
        
        # Count total events
        events_total_result = await db.execute(
            select(func.count(Event.id))
            .where(Event.camera_id == camera.id)
        )
        events_total = events_total_result.scalar() or 0
        
        cameras_with_stats.append(CameraWithStats(
            **CameraResponse.model_validate(camera).model_dump(),
            events_today=events_today,
            events_total=events_total,
            uptime_percentage=0.0  # TODO: Calculate actual uptime
        ))
    
    return cameras_with_stats


@router.post("", response_model=CameraResponse)
async def create_camera(
    camera_create: CameraCreate,
    current_user: User = Depends(require_operator),
    db: AsyncSession = Depends(get_db)
):
    """Create a new camera"""
    camera = Camera(
        **camera_create.model_dump(),
        owner_id=current_user.id,
        status=CameraStatus.OFFLINE
    )
    
    db.add(camera)
    await db.commit()
    await db.refresh(camera)
    
    return camera


@router.get("/{camera_id}", response_model=CameraWithStats)
async def get_camera(
    camera_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get camera by ID"""
    result = await db.execute(
        select(Camera)
        .where(Camera.id == camera_id)
        .where(Camera.owner_id == current_user.id)
    )
    camera = result.scalar_one_or_none()
    
    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera not found"
        )
    
    # Get stats
    today = datetime.utcnow().date()
    events_today_result = await db.execute(
        select(func.count(Event.id))
        .where(Event.camera_id == camera.id)
        .where(func.date(Event.timestamp) == today)
    )
    events_today = events_today_result.scalar() or 0
    
    events_total_result = await db.execute(
        select(func.count(Event.id))
        .where(Event.camera_id == camera.id)
    )
    events_total = events_total_result.scalar() or 0
    
    return CameraWithStats(
        **CameraResponse.model_validate(camera).model_dump(),
        events_today=events_today,
        events_total=events_total,
        uptime_percentage=0.0
    )


@router.put("/{camera_id}", response_model=CameraResponse)
async def update_camera(
    camera_id: int,
    camera_update: CameraUpdate,
    current_user: User = Depends(require_operator),
    db: AsyncSession = Depends(get_db)
):
    """Update camera configuration"""
    result = await db.execute(
        select(Camera)
        .where(Camera.id == camera_id)
        .where(Camera.owner_id == current_user.id)
    )
    camera = result.scalar_one_or_none()
    
    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera not found"
        )
    
    update_data = camera_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(camera, key, value)
    
    await db.commit()
    await db.refresh(camera)
    
    return camera


@router.delete("/{camera_id}")
async def delete_camera(
    camera_id: int,
    current_user: User = Depends(require_operator),
    db: AsyncSession = Depends(get_db)
):
    """Delete a camera"""
    result = await db.execute(
        select(Camera)
        .where(Camera.id == camera_id)
        .where(Camera.owner_id == current_user.id)
    )
    camera = result.scalar_one_or_none()
    
    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera not found"
        )
    
    # Stop stream if running
    stream_manager = get_stream_manager()
    await stream_manager.remove_stream(camera_id)
    
    await db.delete(camera)
    await db.commit()
    
    return {"message": "Camera deleted successfully"}


@router.post("/{camera_id}/test", response_model=CameraTestResult)
async def test_camera_connection(
    camera_id: int,
    current_user: User = Depends(require_operator),
    db: AsyncSession = Depends(get_db)
):
    """Test camera connection"""
    result = await db.execute(
        select(Camera)
        .where(Camera.id == camera_id)
        .where(Camera.owner_id == current_user.id)
    )
    camera = result.scalar_one_or_none()
    
    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera not found"
        )
    
    # Try to connect
    try:
        cap = cv2.VideoCapture(camera.stream_url)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret:
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                fps = int(cap.get(cv2.CAP_PROP_FPS))
                cap.release()
                
                return CameraTestResult(
                    success=True,
                    message="Connection successful",
                    resolution=f"{width}x{height}",
                    fps=fps
                )
        cap.release()
        return CameraTestResult(
            success=False,
            message="Failed to read frame from camera"
        )
    except Exception as e:
        return CameraTestResult(
            success=False,
            message=f"Connection error: {str(e)}"
        )


@router.post("/{camera_id}/start")
async def start_camera_stream(
    camera_id: int,
    current_user: User = Depends(require_operator),
    db: AsyncSession = Depends(get_db)
):
    """Start camera stream"""
    result = await db.execute(
        select(Camera)
        .where(Camera.id == camera_id)
        .where(Camera.owner_id == current_user.id)
    )
    camera = result.scalar_one_or_none()
    
    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera not found"
        )
    
    stream_manager = get_stream_manager()
    handler = await stream_manager.add_stream(
        camera_id=camera.id,
        stream_url=camera.stream_url,
        fps=camera.fps
    )
    
    # Update status
    camera.status = handler.get_status()
    camera.last_seen = datetime.utcnow()
    await db.commit()
    
    return {
        "message": "Stream started",
        "status": camera.status.value
    }


@router.post("/{camera_id}/stop")
async def stop_camera_stream(
    camera_id: int,
    current_user: User = Depends(require_operator),
    db: AsyncSession = Depends(get_db)
):
    """Stop camera stream"""
    result = await db.execute(
        select(Camera)
        .where(Camera.id == camera_id)
        .where(Camera.owner_id == current_user.id)
    )
    camera = result.scalar_one_or_none()
    
    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera not found"
        )
    
    stream_manager = get_stream_manager()
    await stream_manager.remove_stream(camera_id)
    
    camera.status = CameraStatus.DISABLED
    await db.commit()
    
    return {"message": "Stream stopped"}


@router.get("/{camera_id}/stream")
async def stream_camera(
    camera_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get MJPEG stream for camera"""
    result = await db.execute(
        select(Camera)
        .where(Camera.id == camera_id)
        .where(Camera.owner_id == current_user.id)
    )
    camera = result.scalar_one_or_none()
    
    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera not found"
        )
    
    stream_manager = get_stream_manager()
    handler = stream_manager.get_stream(camera_id)
    
    if not handler or not handler.is_connected():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stream not available"
        )
    
    async def generate():
        async for frame in handler.frame_generator():
            _, buffer = cv2.imencode('.jpg', frame)
            yield (
                b'--frame\r\n'
                b'Content-Type: image/jpeg\r\n\r\n' +
                buffer.tobytes() +
                b'\r\n'
            )
    
    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )
