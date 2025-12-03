"""
Chowkidaar NVR - Camera Management Routes
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
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
from app.services.yolo_detector import get_detector
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
    """Create a new camera and automatically start stream"""
    camera = Camera(
        **camera_create.model_dump(),
        owner_id=current_user.id,
        status=CameraStatus.connecting
    )
    
    db.add(camera)
    await db.commit()
    await db.refresh(camera)
    
    # Auto-start stream
    stream_manager = get_stream_manager()
    try:
        handler = await stream_manager.add_stream(
            camera_id=camera.id,
            stream_url=camera.stream_url,
            fps=camera.fps
        )
        camera.status = handler.get_status()
        camera.last_seen = datetime.utcnow()
        await db.commit()
        await db.refresh(camera)
    except Exception as e:
        camera.status = CameraStatus.error
        camera.error_message = str(e)
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
    
    camera.status = CameraStatus.disabled
    await db.commit()
    
    return {"message": "Stream stopped"}


@router.get("/{camera_id}/stream")
async def stream_camera(
    camera_id: int,
    detection: bool = Query(True, description="Enable YOLO detection overlay"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get MJPEG stream for camera with optional detection overlay"""
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
    
    # Auto-start stream if not running
    if not handler or not handler.is_connected():
        handler = await stream_manager.add_stream(
            camera_id=camera.id,
            stream_url=camera.stream_url,
            fps=camera.fps
        )
        # Update camera status
        camera.status = handler.get_status()
        camera.last_seen = datetime.utcnow()
        await db.commit()
        
        # Wait a bit for connection
        await asyncio.sleep(1)
        
        if not handler.is_connected():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Failed to connect to camera stream: {handler.info.error_message or 'Connection timeout'}"
            )
    
    # Get detector if detection enabled
    detector = None
    if detection and camera.detection_enabled:
        detector = await get_detector()
    
    async def generate():
        frame_count = 0
        last_detections = []  # Keep last detections for smooth overlay
        
        async for frame in handler.frame_generator():
            output_frame = frame
            
            # Run detection every 5th frame to reduce CPU load
            if detector and frame_count % 5 == 0:
                try:
                    detection_result = await detector.detect(frame)
                    detections = detection_result.get("objects", [])
                    if detections:
                        last_detections = detections  # Update last detections
                except Exception as e:
                    pass  # Silently continue on detection errors
            
            # Always draw last known detections
            if detector and last_detections:
                output_frame = detector.draw_detections(frame, last_detections)
            
            frame_count += 1
            _, buffer = cv2.imencode('.jpg', output_frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
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
