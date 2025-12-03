"""
Chowkidaar NVR - API Routes Module
"""
from fastapi import APIRouter
from app.api.routes import auth, users, cameras, events, assistant, system

api_router = APIRouter(prefix="/api/v1")

# Include all route modules
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(cameras.router)
api_router.include_router(events.router)
api_router.include_router(assistant.router)
api_router.include_router(system.router)
