"""
Chowkidaar NVR - System Monitoring Routes
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db, async_engine
from app.models.user import User
from app.models.camera import Camera
from app.schemas.system import SystemStats, SystemHealth, InferenceStats
from app.api.deps import get_current_user, require_admin
from app.services.system_monitor import get_system_monitor
from app.services.stream_handler import get_stream_manager
from app.services.yolo_detector import get_detector
from app.services.ollama_vlm import get_vlm_service

router = APIRouter(prefix="/system", tags=["System"])


@router.get("/stats", response_model=SystemStats)
async def get_system_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current system statistics"""
    monitor = get_system_monitor()
    stream_manager = get_stream_manager()
    
    # Get camera count
    result = await db.execute(
        select(func.count(Camera.id))
        .where(Camera.owner_id == current_user.id)
    )
    total_cameras = result.scalar() or 0
    
    # Get inference stats if available
    inference_stats = None
    try:
        detector = await get_detector()
        stats = detector.get_stats()
        if stats["inference_count"] > 0:
            inference_stats = InferenceStats(**stats)
    except:
        pass
    
    return await monitor.get_system_stats(
        active_streams=stream_manager.get_active_count(),
        total_cameras=total_cameras,
        inference_stats=inference_stats
    )


@router.get("/health", response_model=SystemHealth)
async def get_system_health(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get system health status"""
    monitor = get_system_monitor()
    
    # Check database
    db_healthy = True
    try:
        await db.execute(select(1))
    except:
        db_healthy = False
    
    # Check Ollama
    ollama_healthy = False
    try:
        vlm_service = await get_vlm_service()
        ollama_healthy = await vlm_service.check_health()
    except:
        pass
    
    return await monitor.check_health(
        db_healthy=db_healthy,
        ollama_healthy=ollama_healthy
    )


@router.get("/streams")
async def get_active_streams(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get information about active streams"""
    stream_manager = get_stream_manager()
    streams = stream_manager.get_all_streams()
    
    # Get user's camera IDs
    result = await db.execute(
        select(Camera.id)
        .where(Camera.owner_id == current_user.id)
    )
    user_camera_ids = set(row[0] for row in result.all())
    
    # Filter to user's streams
    stream_info = []
    for camera_id, handler in streams.items():
        if camera_id in user_camera_ids:
            info = handler.info
            stream_info.append({
                "camera_id": info.camera_id,
                "state": info.state.value,
                "fps": info.fps,
                "resolution": info.resolution,
                "frame_count": info.frame_count,
                "last_frame_time": info.last_frame_time.isoformat() if info.last_frame_time else None,
                "error": info.error_message
            })
    
    return {
        "active_count": len(stream_info),
        "streams": stream_info
    }


@router.get("/models")
async def get_available_models(
    current_user: User = Depends(get_current_user)
):
    """Get list of available Ollama models"""
    try:
        vlm_service = await get_vlm_service()
        models = await vlm_service.list_models()
        return {"models": models}
    except Exception as e:
        return {"models": [], "error": str(e)}


@router.get("/info")
async def get_system_info(
    current_user: User = Depends(require_admin)
):
    """Get system information (admin only)"""
    import platform
    import sys
    from app.core.config import settings
    
    return {
        "app_name": settings.app_name,
        "app_version": settings.app_version,
        "python_version": sys.version,
        "platform": platform.platform(),
        "processor": platform.processor(),
        "yolo_model": settings.yolo_model_path,
        "vlm_model": settings.ollama_vlm_model,
        "chat_model": settings.ollama_chat_model,
        "max_streams": settings.max_concurrent_streams
    }


@router.post("/restart-detector")
async def restart_detector(
    current_user: User = Depends(require_admin)
):
    """Restart the YOLO detector (admin only)"""
    try:
        from app.services.yolo_detector import detector
        await detector.shutdown()
        await detector.initialize()
        return {"message": "Detector restarted successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to restart detector: {str(e)}"
        )


@router.post("/clear-streams")
async def clear_all_streams(
    current_user: User = Depends(require_admin)
):
    """Stop all active streams (admin only)"""
    try:
        stream_manager = get_stream_manager()
        await stream_manager.stop_all()
        return {"message": "All streams stopped"}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to stop streams: {str(e)}"
        )
