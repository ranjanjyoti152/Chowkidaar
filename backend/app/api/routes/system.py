"""
Chowkidaar NVR - System Monitoring Routes
"""
from typing import List
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import shutil
import os

from app.core.database import get_db, async_engine
from app.core.config import settings
from app.models.user import User
from app.models.camera import Camera
from app.schemas.system import SystemStats, SystemHealth, InferenceStats
from app.api.deps import get_current_user, require_admin
from app.services.system_monitor import get_system_monitor
from app.services.stream_handler import get_stream_manager
from app.services.yolo_detector import get_detector
from app.services.vlm_service import get_unified_vlm_service

router = APIRouter(prefix="/system", tags=["System"])

# Models directory
MODELS_DIR = Path("models")
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
    
    # Check VLM service (unified)
    vlm_healthy = False
    try:
        vlm_service = get_unified_vlm_service()
        vlm_healthy = await vlm_service.check_health()
    except:
        pass
    
    return await monitor.check_health(
        db_healthy=db_healthy,
        ollama_healthy=vlm_healthy
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
    """Get list of available models from unified VLM service"""
    try:
        vlm_service = get_unified_vlm_service()
        models = await vlm_service.list_models()
        return {"models": models}
    except Exception as e:
        return {"models": [], "error": str(e)}


@router.post("/ollama/test")
async def test_ollama_connection(
    current_user: User = Depends(get_current_user),
    url: str = None
):
    """Test Ollama connection and get available models"""
    import httpx
    
    test_url = url or settings.ollama_base_url
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{test_url}/api/tags")
            if response.status_code == 200:
                data = response.json()
                models = [m["name"] for m in data.get("models", [])]
                return {
                    "status": "online",
                    "url": test_url,
                    "models": models,
                    "model_count": len(models)
                }
            else:
                return {
                    "status": "error",
                    "url": test_url,
                    "models": [],
                    "error": f"HTTP {response.status_code}"
                }
    except Exception as e:
        return {
            "status": "offline",
            "url": test_url,
            "models": [],
            "error": str(e)
        }


@router.post("/llm/test")
async def test_llm_provider(
    current_user: User = Depends(get_current_user),
    provider: str = "ollama",
    url: str = None,
    api_key: str = None,
    model: str = None
):
    """Test any LLM provider connection (Ollama, OpenAI, Gemini)"""
    from loguru import logger
    logger.info(f"Testing LLM provider: {provider}, api_key present: {bool(api_key)}, url: {url}")
    try:
        vlm_service = get_unified_vlm_service()
        result = await vlm_service.test_provider(
            provider=provider,
            ollama_url=url,
            model=model,
            openai_api_key=api_key if provider == "openai" else None,
            openai_model=model if provider == "openai" else None,
            openai_base_url=url if provider == "openai" else None,
            gemini_api_key=api_key if provider == "gemini" else None,
            gemini_model=model if provider == "gemini" else None
        )
        logger.info(f"Test result: {result}")
        result["provider"] = provider
        return result
    except Exception as e:
        logger.error(f"LLM test error: {e}")
        return {
            "status": "error",
            "provider": provider,
            "models": [],
            "error": str(e)
        }


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


@router.get("/yolo-models")
async def list_yolo_models(
    current_user: User = Depends(get_current_user)
):
    """List available YOLO models"""
    models = []
    
    # Built-in models
    builtin_models = [
        {"name": "yolov8n", "display_name": "YOLOv8n (Nano - Fast)", "type": "builtin", "size": "6 MB"},
        {"name": "yolov8s", "display_name": "YOLOv8s (Small)", "type": "builtin", "size": "22 MB"},
        {"name": "yolov8m", "display_name": "YOLOv8m (Medium)", "type": "builtin", "size": "52 MB"},
        {"name": "yolov8l", "display_name": "YOLOv8l (Large)", "type": "builtin", "size": "87 MB"},
        {"name": "yolov8x", "display_name": "YOLOv8x (XLarge)", "type": "builtin", "size": "137 MB"},
    ]
    models.extend(builtin_models)
    
    # Custom models from models directory
    if MODELS_DIR.exists():
        for model_file in MODELS_DIR.glob("*.pt"):
            size_mb = model_file.stat().st_size / (1024 * 1024)
            models.append({
                "name": model_file.stem,
                "display_name": f"{model_file.stem} (Custom)",
                "type": "custom",
                "size": f"{size_mb:.1f} MB",
                "path": str(model_file)
            })
    
    return {"models": models}


@router.post("/yolo-models/upload")
async def upload_yolo_model(
    file: UploadFile = File(...),
    name: str = Form(None),
    current_user: User = Depends(require_admin)
):
    """Upload a custom YOLO model (.pt file)"""
    if not file.filename.endswith('.pt'):
        raise HTTPException(
            status_code=400,
            detail="Only .pt files are allowed"
        )
    
    # Use provided name or filename
    model_name = name or file.filename.replace('.pt', '')
    model_path = MODELS_DIR / f"{model_name}.pt"
    
    # Check if already exists
    if model_path.exists():
        raise HTTPException(
            status_code=400,
            detail=f"Model '{model_name}' already exists"
        )
    
    # Save file
    try:
        with open(model_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        size_mb = model_path.stat().st_size / (1024 * 1024)
        
        return {
            "message": "Model uploaded successfully",
            "model": {
                "name": model_name,
                "display_name": f"{model_name} (Custom)",
                "type": "custom",
                "size": f"{size_mb:.1f} MB",
                "path": str(model_path)
            }
        }
    except Exception as e:
        if model_path.exists():
            model_path.unlink()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save model: {str(e)}"
        )


@router.delete("/yolo-models/{model_name}")
async def delete_yolo_model(
    model_name: str,
    current_user: User = Depends(require_admin)
):
    """Delete a custom YOLO model"""
    model_path = MODELS_DIR / f"{model_name}.pt"
    
    if not model_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Model '{model_name}' not found"
        )
    
    try:
        model_path.unlink()
        return {"message": f"Model '{model_name}' deleted successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete model: {str(e)}"
        )


@router.get("/yolo-models/{model_name}/classes")
async def get_model_classes(
    model_name: str,
    current_user: User = Depends(get_current_user)
):
    """Get classes for a YOLO model"""
    try:
        from ultralytics import YOLO
        
        # Determine model path
        if model_name.startswith("yolov8"):
            model_path = f"{model_name}.pt"
        else:
            model_path = MODELS_DIR / f"{model_name}.pt"
            if not model_path.exists():
                raise HTTPException(status_code=404, detail=f"Model '{model_name}' not found")
            model_path = str(model_path)
        
        # Load model and get classes
        model = YOLO(model_path)
        classes = model.names  # dict {0: 'person', 1: 'bicycle', ...}
        
        return {
            "model": model_name,
            "classes": list(classes.values()),
            "class_count": len(classes)
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load model classes: {str(e)}"
        )


@router.post("/yolo-models/{model_name}/activate")
async def activate_yolo_model(
    model_name: str,
    current_user: User = Depends(require_admin)
):
    """Activate/switch to a YOLO model"""
    try:
        from app.services.yolo_detector import detector
        
        # Determine model path
        if model_name.startswith("yolov8"):
            model_path = f"{model_name}.pt"
        else:
            model_path = MODELS_DIR / f"{model_name}.pt"
            if not model_path.exists():
                raise HTTPException(status_code=404, detail=f"Model '{model_name}' not found")
            model_path = str(model_path)
        
        # Reload detector with new model
        await detector.shutdown()
        detector._model_path = model_path
        await detector.initialize()
        
        return {
            "message": f"Model '{model_name}' activated successfully",
            "model": model_name
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to activate model: {str(e)}"
        )
