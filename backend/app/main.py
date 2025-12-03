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
from app.core.database import init_db, close_db
from app.api import api_router
from app.services.yolo_detector import get_detector
from app.services.stream_handler import get_stream_manager
from app.services.ollama_vlm import get_vlm_service


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
    
    # Create storage directories
    Path(settings.events_storage_path).mkdir(parents=True, exist_ok=True)
    Path(settings.frames_storage_path).mkdir(parents=True, exist_ok=True)
    Path("logs").mkdir(exist_ok=True)
    
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
    
    # Check Ollama connection
    logger.info("Checking Ollama connection...")
    try:
        vlm_service = await get_vlm_service()
        if await vlm_service.check_health():
            models = await vlm_service.list_models()
            logger.info(f"✅ Ollama connected. Available models: {models}")
        else:
            logger.warning("⚠️ Ollama not available")
    except Exception as e:
        logger.error(f"❌ Ollama error: {e}")
    
    logger.info(f"🛡️ {settings.app_name} is ready!")
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")
    
    # Stop all streams
    stream_manager = get_stream_manager()
    await stream_manager.stop_all()
    
    # Close database
    await close_db()
    
    # Close VLM service
    vlm_service = await get_vlm_service()
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
