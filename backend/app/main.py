"""
Chowkidaar NVR - Main Application
AI-Powered Network Video Recorder System with V-JEPA 2
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
from app.services.vjepa2_service import get_vjepa2_service, VJEPA2Service
from app.services.stream_handler import get_stream_manager
from app.services.detection_service import get_detection_service
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
    
    # Initialize V-JEPA 2 detector
    logger.info("Loading V-JEPA 2 model...")
    try:
        vjepa2_service = await get_vjepa2_service()
        
        # Get model name from settings or use default
        model_name = "vjepa2-large"  # Default model
        try:
            from app.models.settings import UserSettings
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(UserSettings).limit(1)
                )
                user_settings = result.scalar_one_or_none()
                if user_settings and hasattr(user_settings, 'vjepa2_model'):
                    model_name = user_settings.vjepa2_model or "vjepa2-large"
        except Exception as e:
            logger.warning(f"Using default V-JEPA 2 model: {e}")
        
        if await vjepa2_service.initialize(model_name=model_name):
            logger.info(f"✅ V-JEPA 2 initialized: {model_name}")
        else:
            logger.warning("⚠️ V-JEPA 2 failed to initialize")
    except Exception as e:
        logger.error(f"❌ V-JEPA 2 error: {e}")
    
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
    
    # Shutdown V-JEPA 2 service
    try:
        vjepa2_service = await get_vjepa2_service()
        await vjepa2_service.shutdown()
        logger.info("V-JEPA 2 service stopped")
    except Exception as e:
        logger.error(f"Error stopping V-JEPA 2 service: {e}")
    
    # Close database
    await close_db()
    
    logger.info("👋 Goodbye!")


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="AI-Powered Network Video Recorder with V-JEPA 2 Video Understanding",
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
        "description": "AI-Powered Network Video Recorder with V-JEPA 2",
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
