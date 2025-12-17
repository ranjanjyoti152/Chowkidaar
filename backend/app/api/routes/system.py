"""
Chowkidaar NVR - System Monitoring Routes
"""
from typing import List
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from loguru import logger
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
from app.services.owlv2_detector import OWLv2Detector, get_owlv2_detector

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
    """Restart the YOLO detector and all detection loops (admin only)"""
    try:
        from app.services.yolo_detector import detector
        from app.services.detection_service import get_detection_service
        
        # Restart the detector
        await detector.shutdown()
        await detector.initialize()
        
        # Restart all detection loops to pick up new model from settings
        detection_service = await get_detection_service()
        await detection_service.restart_all_detection_loops()
        
        return {"message": "Detector and all detection loops restarted successfully"}
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
    """List available detection models (YOLO and OWLv2)"""
    models = []
    
    # Built-in YOLO models
    builtin_models = [
        {"name": "yolov8n", "display_name": "YOLOv8n (Nano - Fast)", "type": "builtin", "size": "6 MB", "category": "yolo"},
        {"name": "yolov8s", "display_name": "YOLOv8s (Small)", "type": "builtin", "size": "22 MB", "category": "yolo"},
        {"name": "yolov8m", "display_name": "YOLOv8m (Medium)", "type": "builtin", "size": "52 MB", "category": "yolo"},
        {"name": "yolov8l", "display_name": "YOLOv8l (Large)", "type": "builtin", "size": "87 MB", "category": "yolo"},
        {"name": "yolov8x", "display_name": "YOLOv8x (XLarge)", "type": "builtin", "size": "137 MB", "category": "yolo"},
    ]
    models.extend(builtin_models)
    
    # OWLv2 Open-Vocabulary Detection models
    owlv2_models = [
        {"name": "owlv2-base", "display_name": "OWLv2 Base (Open-Vocab)", "type": "builtin", "size": "~600 MB", "category": "owlv2", "description": "Open-vocabulary detection - detect any object by text description"},
        {"name": "owlv2-large", "display_name": "OWLv2 Large (Open-Vocab)", "type": "builtin", "size": "~1.2 GB", "category": "owlv2", "description": "Larger model for better accuracy on custom queries"},
    ]
    models.extend(owlv2_models)
    
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


@router.get("/owlv2-status")
async def get_owlv2_model_status(
    current_user: User = Depends(get_current_user)
):
    """Check OWLv2 model download status"""
    from pathlib import Path
    
    cache_dir = Path.home() / ".cache" / "huggingface" / "hub"
    
    models_status = {}
    for model_name, model_id in OWLv2Detector.AVAILABLE_MODELS.items():
        model_cache_name = f"models--{model_id.replace('/', '--')}"
        is_cached = (cache_dir / model_cache_name).exists()
        
        # Estimate size
        size = "~600 MB" if "base" in model_name else "~1.2 GB"
        
        models_status[model_name] = {
            "model_id": model_id,
            "cached": is_cached,
            "size": size,
            "cache_path": str(cache_dir / model_cache_name) if is_cached else None
        }
    
    return {
        "models": models_status,
        "cache_directory": str(cache_dir)
    }


@router.get("/detector-status")
async def get_detector_status(
    current_user: User = Depends(get_current_user)
):
    """Get status of all detectors - shows which one is active"""
    try:
        yolo = await get_detector()
        owlv2 = await get_owlv2_detector()
        
        yolo_active = yolo._initialized if hasattr(yolo, '_initialized') else False
        owlv2_active = owlv2._initialized if hasattr(owlv2, '_initialized') else False
        
        # Determine active detector
        active_detector = None
        if owlv2_active:
            active_detector = "owlv2"
        elif yolo_active:
            active_detector = "yolo"
        
        return {
            "active_detector": active_detector,
            "yolo": {
                "initialized": yolo_active,
                "model": getattr(yolo, '_model_path', None) if yolo_active else None
            },
            "owlv2": {
                "initialized": owlv2_active,
                "model": owlv2._current_model_name if owlv2_active else None,
                "queries": owlv2.get_active_queries() if owlv2_active else []
            }
        }
    except Exception as e:
        logger.error(f"Error getting detector status: {e}")
        return {
            "active_detector": None,
            "error": str(e)
        }


@router.post("/owlv2-download/{model_name}")
async def download_owlv2_model(
    model_name: str,
    current_user: User = Depends(require_admin)
):
    """Download/pre-cache an OWLv2 model"""
    if model_name not in OWLv2Detector.AVAILABLE_MODELS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid model name. Available: {list(OWLv2Detector.AVAILABLE_MODELS.keys())}"
        )
    
    try:
        success = await OWLv2Detector.preload_model(model_name)
        if success:
            return {"status": "success", "message": f"OWLv2 model '{model_name}' downloaded successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to download model")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
    """Get classes for a YOLO model or queries for OWLv2"""
    try:
        # OWLv2 returns active queries instead of fixed classes
        if model_name.startswith("owlv2"):
            from app.services.owlv2_detector import get_owlv2_detector
            
            owlv2 = await get_owlv2_detector()
            queries = owlv2.get_active_queries()
            
            return {
                "model": model_name,
                "classes": queries,  # For UI compatibility
                "queries": queries,
                "class_count": len(queries),
                "type": "owlv2",
                "note": "OWLv2 uses text queries for open-vocabulary detection. You can customize these in settings."
            }
        
        # YOLO model classes
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
            "class_count": len(classes),
            "type": "yolo"
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
    """Activate/switch to a YOLO or OWLv2 model - only one can be active at a time"""
    try:
        # Check if it's an OWLv2 model
        if model_name.startswith("owlv2"):
            from app.services.owlv2_detector import get_owlv2_detector
            from app.services.yolo_detector import get_detector
            
            # First, deactivate YOLO detector
            try:
                yolo = await get_detector()
                if yolo._initialized:
                    await yolo.shutdown()
                    logger.info("🔴 YOLO detector deactivated (switching to OWLv2)")
            except Exception as e:
                logger.warning(f"Could not deactivate YOLO: {e}")
            
            # Now activate OWLv2
            owlv2 = await get_owlv2_detector()
            success = await owlv2.initialize(model_name=model_name)
            
            if success:
                # Restart all detection loops to use the new model
                from app.services.detection_service import get_detection_service
                detection_service = await get_detection_service()
                await detection_service.restart_all_detection_loops()
                
                return {
                    "message": f"OWLv2 model '{model_name}' activated successfully. YOLO deactivated.",
                    "model": model_name,
                    "type": "owlv2",
                    "yolo_status": "deactivated"
                }
            else:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to initialize OWLv2 model '{model_name}'"
                )
        
        # YOLO model activation - deactivate OWLv2 first
        from app.services.yolo_detector import get_detector
        from app.services.owlv2_detector import get_owlv2_detector
        
        # Deactivate OWLv2 if active
        try:
            owlv2 = await get_owlv2_detector()
            if owlv2._initialized:
                owlv2._initialized = False
                owlv2.model = None
                owlv2.processor = None
                logger.info("🔴 OWLv2 detector deactivated (switching to YOLO)")
        except Exception as e:
            logger.warning(f"Could not deactivate OWLv2: {e}")
        
        detector = await get_detector()
        
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
        detector.model_path = model_path  # Fixed: was _model_path
        await detector.initialize()
        
        # Restart all detection loops to use the new model
        from app.services.detection_service import get_detection_service
        detection_service = await get_detection_service()
        await detection_service.restart_all_detection_loops()
        
        return {
            "message": f"YOLO model '{model_name}' activated successfully. OWLv2 deactivated.",
            "model": model_name,
            "type": "yolo",
            "owlv2_status": "deactivated"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to activate model: {str(e)}"
        )
