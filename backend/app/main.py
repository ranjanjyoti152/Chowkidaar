"""
Chowkidaar NVR - Main Application
AI-Powered Network Video Recorder System
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from loguru import logger
import sys
from pathlib import Path

from app.core.config import settings
from app.core.database import init_db, close_db, AsyncSessionLocal
from app.api import api_router
from app.services.yolo_detector import get_detector
from app.services.stream_handler import get_stream_manager
from app.services.vlm_service import get_unified_vlm_service
from app.services.detection_service import get_detection_service
from app.services.owlv2_detector import OWLv2Detector
from app.services.embedding_service import get_embedding_service, initialize_embeddings_from_db
from sqlalchemy import select


# Configure logging
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="DEBUG" if settings.debug else "INFO"
)
logger.add(
    "logs/chowkidaar.log",
    rotation="10 MB",
    retention="7 days",
    level="DEBUG"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler"""
    logger.info(f"🚀 Starting {settings.app_name} v{settings.app_version}")
    
    # Ensure all required directories exist (already done on config import, but double-check)
    settings.ensure_directories()
    logger.info(f"📁 Storage directories ready at: {settings.base_path}/storage")
    
    # Initialize database
    logger.info("Initializing database...")
    await init_db()
    
    # Initialize YOLO detector
    logger.info("Loading YOLO model...")
    try:
        detector = await get_detector()
        if detector._initialized:
            logger.info("✅ YOLO detector initialized")
        else:
            logger.warning("⚠️ YOLO detector failed to initialize")
    except Exception as e:
        logger.error(f"❌ YOLO detector error: {e}")
    
    # Pre-download OWLv2 models (if not cached)
    logger.info("Checking OWLv2 models...")
    try:
        # Pre-download base model (most commonly used)
        await OWLv2Detector.preload_model("owlv2-base")
        logger.info("✅ OWLv2 models ready")
    except Exception as e:
        logger.warning(f"⚠️ OWLv2 preload skipped: {e}")
    
    # Check VLM service connection
    logger.info("Checking VLM service connection...")
    try:
        unified_vlm_service = get_unified_vlm_service()
        if await unified_vlm_service.check_health():
            models = await unified_vlm_service.list_models()
            logger.info(f"✅ VLM service connected. Available models: {models}")
        else:
            logger.warning("⚠️ VLM service not available")
    except Exception as e:
        logger.error(f"❌ VLM service error: {e}")
    
    # Load VLM settings from database and configure unified VLM service
    logger.info("Loading VLM settings from database...")
    try:
        from app.models.settings import UserSettings
        from app.models.user import User
        async with AsyncSessionLocal() as db:
            # First try to get admin user's settings (most authoritative)
            admin_result = await db.execute(
                select(UserSettings)
                .join(User, UserSettings.user_id == User.id)
                .where(User.role == 'admin')
                .order_by(UserSettings.updated_at.desc())
                .limit(1)
            )
            user_settings = admin_result.scalar_one_or_none()
            
            # Fall back to any user settings if no admin settings exist
            if not user_settings:
                result = await db.execute(
                    select(UserSettings)
                    .order_by(UserSettings.updated_at.desc())
                    .limit(1)
                )
                user_settings = result.scalar_one_or_none()
            
            if user_settings:
                provider = getattr(user_settings, 'vlm_provider', 'ollama')
                logger.info(f"Found saved VLM settings: provider={provider}, model={user_settings.vlm_model}, url={user_settings.vlm_url}")
                unified_vlm_service.configure(
                    provider=provider,
                    ollama_url=user_settings.vlm_url,
                    ollama_model=user_settings.vlm_model,
                    openai_api_key=getattr(user_settings, 'openai_api_key', None),
                    openai_model=getattr(user_settings, 'openai_model', 'gpt-4o'),
                    openai_base_url=getattr(user_settings, 'openai_base_url', None),
                    gemini_api_key=getattr(user_settings, 'gemini_api_key', None),
                    gemini_model=getattr(user_settings, 'gemini_model', 'gemini-2.0-flash-exp')
                )
                logger.info(f"✅ VLM service configured from saved settings: provider={provider}")
            else:
                logger.warning("⚠️ No VLM settings found in database, using defaults (Ollama)")
    except Exception as e:
        logger.error(f"❌ Error loading VLM settings: {e}")
    
    # Start all enabled camera streams automatically
    logger.info("Starting enabled camera streams...")
    try:
        from app.models.camera import Camera
        stream_manager = get_stream_manager()
        
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Camera).where(Camera.is_enabled == True)
            )
            cameras = result.scalars().all()
            
            started_count = 0
            for camera in cameras:
                try:
                    logger.info(f"Starting stream for camera {camera.id}: {camera.name}")
                    await stream_manager.add_stream(
                        camera_id=camera.id,
                        stream_url=camera.stream_url,
                        fps=camera.fps or 15
                    )
                    started_count += 1
                except Exception as e:
                    logger.error(f"Failed to start camera {camera.id}: {e}")
            
            logger.info(f"✅ Started {started_count}/{len(cameras)} camera streams")
    except Exception as e:
        logger.error(f"❌ Error starting camera streams: {e}")
    
    # Start detection service
    logger.info("Starting detection service...")
    try:
        detection_service = await get_detection_service()
        await detection_service.start()
        logger.info("✅ Detection service started")
    except Exception as e:
        logger.error(f"❌ Detection service error: {e}")
    
    # Initialize embedding service for semantic search
    logger.info("Initializing embedding service...")
    try:
        embedding_service = get_embedding_service()
        if embedding_service.is_available():
            async with AsyncSessionLocal() as db:
                await initialize_embeddings_from_db(db)
            logger.info(f"✅ Embedding service ready with {len(embedding_service.event_embeddings)} indexed events")
        else:
            logger.warning("⚠️ Embedding service not available (install: pip install sentence-transformers)")
    except Exception as e:
        logger.warning(f"⚠️ Embedding service skipped: {e}")
    
    logger.info(f"🛡️ {settings.app_name} is ready!")
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")
    
    # Stop detection service
    try:
        detection_service = await get_detection_service()
        await detection_service.stop()
        logger.info("Detection service stopped")
    except Exception as e:
        logger.error(f"Error stopping detection service: {e}")
    
    # Stop all streams
    stream_manager = get_stream_manager()
    await stream_manager.stop_all()
    
    # Close database
    await close_db()
    
    # Close VLM service
    vlm_service = get_unified_vlm_service()
    await vlm_service.close()
    
    logger.info("👋 Goodbye!")


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="AI-Powered Network Video Recorder with YOLOv8+ Detection and VLM Summarization",
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "message": str(exc) if settings.debug else "An unexpected error occurred"
        }
    )


# Include API routes
app.include_router(api_router)


# Health check endpoint
@app.get("/health")
async def health_check():
    """Basic health check endpoint"""
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.app_version
    }


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with app info"""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "description": "AI-Powered Network Video Recorder",
        "docs": "/api/docs",
        "health": "/health"
    }


# Mount static files for frames/thumbnails
frames_path = Path(settings.frames_storage_path)
if frames_path.exists():
    app.mount("/static/frames", StaticFiles(directory=str(frames_path)), name="frames")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level="debug" if settings.debug else "info"
    )
