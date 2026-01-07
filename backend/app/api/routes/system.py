"""
Chowkidaar NVR - System Monitoring Routes
"""
from typing import List
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from loguru import logger

from app.core.database import get_db
from app.core.config import settings
from app.models.user import User
from app.models.camera import Camera
from app.schemas.system import SystemStats, SystemHealth, InferenceStats
from app.api.deps import get_current_user, require_admin
from app.services.system_monitor import get_system_monitor
from app.services.stream_handler import get_stream_manager
from app.services.vjepa2_service import get_vjepa2_service, VJEPA2Service

router = APIRouter(prefix="/system", tags=["System"])

# Models directory - use absolute path from settings
MODELS_DIR = Path(settings.models_path)
MODELS_DIR.mkdir(exist_ok=True)


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
    
    # Get inference stats from V-JEPA 2
    inference_stats = None
    try:
        vjepa2 = await get_vjepa2_service()
        stats = vjepa2.get_stats()
        if stats.get("inference_count", 0) > 0:
            inference_stats = InferenceStats(
                model=stats.get("model", "vjepa2"),
                device=stats.get("device", "cuda"),
                inference_count=stats.get("inference_count", 0),
                average_inference_time=stats.get("average_inference_time_ms", 0),
                last_inference_time=stats.get("last_inference_time_ms", 0)
            )
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
    
    # Check V-JEPA 2 service
    vjepa2_healthy = False
    try:
        vjepa2 = await get_vjepa2_service()
        vjepa2_healthy = vjepa2.initialized
    except:
        pass
    
    return await monitor.check_health(
        db_healthy=db_healthy,
        ollama_healthy=vjepa2_healthy  # Reusing field for V-JEPA 2
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
    """Get list of available V-JEPA 2 models"""
    models = list(VJEPA2Service.AVAILABLE_MODELS.keys())
    return {"models": models, "type": "vjepa2"}


@router.get("/info")
async def get_system_info(
    current_user: User = Depends(require_admin)
):
    """Get system information (admin only)"""
    import platform
    import sys
    
    # Get V-JEPA 2 status
    vjepa2 = await get_vjepa2_service()
    
    return {
        "app_name": settings.app_name,
        "app_version": settings.app_version,
        "python_version": sys.version,
        "platform": platform.platform(),
        "processor": platform.processor(),
        "detection_model": "V-JEPA 2",
        "vjepa2_model": vjepa2.model_name if vjepa2.initialized else None,
        "vjepa2_device": vjepa2.device,
        "vjepa2_initialized": vjepa2.initialized,
        "max_streams": settings.max_concurrent_streams
    }


@router.post("/restart-detector")
async def restart_detector(
    current_user: User = Depends(require_admin)
):
    """Restart the V-JEPA 2 detector and all detection loops (admin only)"""
    try:
        from app.services.detection_service import get_detection_service
        
        # Get V-JEPA 2 service and reinitialize
        vjepa2 = await get_vjepa2_service()
        await vjepa2.shutdown()
        await vjepa2.initialize()
        
        # Restart all detection loops
        detection_service = await get_detection_service()
        await detection_service.restart_all_detection_loops()
        
        return {"message": "V-JEPA 2 detector and all detection loops restarted successfully"}
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


@router.get("/vjepa2-models")
async def list_vjepa2_models(
    current_user: User = Depends(get_current_user)
):
    """List available V-JEPA 2 models"""
    models = []
    
    for name, model_id in VJEPA2Service.AVAILABLE_MODELS.items():
        # Estimate sizes
        if "large" in name:
            size = "~2 GB"
        elif "huge" in name:
            size = "~4 GB"
        elif "giant" in name:
            size = "~8 GB"
        else:
            size = "~2 GB"
            
        models.append({
            "name": name,
            "display_name": f"V-JEPA 2 {name.replace('vjepa2-', '').title()}",
            "model_id": model_id,
            "type": "vjepa2",
            "size": size,
            "description": "Self-supervised video understanding model"
        })
    
    return {"models": models}


@router.get("/vjepa2-status")
async def get_vjepa2_status(
    current_user: User = Depends(get_current_user)
):
    """Get V-JEPA 2 model status"""
    from pathlib import Path
    
    vjepa2 = await get_vjepa2_service()
    stats = vjepa2.get_stats()
    
    cache_dir = Path.home() / ".cache" / "huggingface" / "hub"
    
    models_status = {}
    for model_name, model_id in VJEPA2Service.AVAILABLE_MODELS.items():
        model_cache_name = f"models--{model_id.replace('/', '--')}"
        is_cached = (cache_dir / model_cache_name).exists()
        
        models_status[model_name] = {
            "model_id": model_id,
            "cached": is_cached,
            "active": vjepa2.model_name == model_name and vjepa2.initialized
        }
    
    return {
        "initialized": vjepa2.initialized,
        "current_model": vjepa2.model_name,
        "device": vjepa2.device,
        "stats": stats,
        "models": models_status,
        "cache_directory": str(cache_dir)
    }


@router.post("/vjepa2-download/{model_name}")
async def download_vjepa2_model(
    model_name: str,
    current_user: User = Depends(require_admin)
):
    """Download/pre-cache a V-JEPA 2 model"""
    if model_name not in VJEPA2Service.AVAILABLE_MODELS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid model name. Available: {list(VJEPA2Service.AVAILABLE_MODELS.keys())}"
        )
    
    try:
        success = await VJEPA2Service.preload_model(model_name)
        if success:
            return {"status": "success", "message": f"V-JEPA 2 model '{model_name}' downloaded successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to download model")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/vjepa2-models/{model_name}/activate")
async def activate_vjepa2_model(
    model_name: str,
    current_user: User = Depends(require_admin)
):
    """Activate/switch to a V-JEPA 2 model"""
    if model_name not in VJEPA2Service.AVAILABLE_MODELS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid model name. Available: {list(VJEPA2Service.AVAILABLE_MODELS.keys())}"
        )
    
    try:
        vjepa2 = await get_vjepa2_service()
        
        # Shutdown current model if initialized
        if vjepa2.initialized:
            await vjepa2.shutdown()
        
        # Initialize with new model
        success = await vjepa2.initialize(model_name=model_name)
        
        if success:
            # Restart all detection loops
            from app.services.detection_service import get_detection_service
            detection_service = await get_detection_service()
            await detection_service.restart_all_detection_loops()
            
            return {
                "message": f"V-JEPA 2 model '{model_name}' activated successfully",
                "model": model_name,
                "device": vjepa2.device
            }
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to initialize V-JEPA 2 model '{model_name}'"
            )
    except Exception as e:
        logger.error(f"Error activating V-JEPA 2 model: {e}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
