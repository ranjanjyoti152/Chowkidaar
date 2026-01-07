"""
Chowkidaar NVR - Background Detection Service
Handles automatic event creation from V-JEPA 2 video analysis
"""
import asyncio
from typing import Dict, Optional, List, Set, Any
from datetime import datetime, timedelta
from loguru import logger
import cv2
import numpy as np
from pathlib import Path
import uuid

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from sqlalchemy import select, update
from app.services.vjepa2_service import get_vjepa2_service, VJEPA2Service
from app.services.stream_handler import get_stream_manager
from app.services.notification_service import send_event_notification
from app.models.event import Event, EventType, EventSeverity
from app.models.camera import Camera
from app.models.settings import UserSettings


class DetectionService:
    """Background service for V-JEPA 2 detection and event creation"""
    
    def __init__(self):
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._camera_tasks: Dict[int, asyncio.Task] = {}
        self._last_event_time: Dict[str, datetime] = {}  # "camera_id:class" -> last time
        self._event_cooldown = 10  # seconds between same class events per camera
        
        # Settings cache to reduce database queries
        self._settings_cache: Dict[int, Dict] = {}  # user_id -> settings dict
        self._settings_cache_time: Dict[int, datetime] = {}  # user_id -> last cache time
        self._settings_cache_ttl = 60  # Cache settings for 60 seconds
    
    async def start(self):
        """Start the detection service"""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._main_loop())
        logger.info("Detection service started")
    
    async def stop(self):
        """Stop the detection service"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        # Stop all camera tasks
        for task in self._camera_tasks.values():
            task.cancel()
        self._camera_tasks.clear()
        logger.info("Detection service stopped")
    
    async def restart_all_detection_loops(self):
        """Restart all detection loops to pick up new model settings"""
        logger.info("🔄 Restarting all detection loops to pick up new model...")
        
        # Cancel all existing camera tasks
        for camera_id, task in list(self._camera_tasks.items()):
            logger.info(f"Cancelling detection loop for camera {camera_id}")
            task.cancel()
            try:
                await asyncio.wait_for(task, timeout=2.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
            except Exception as e:
                logger.warning(f"Error cancelling task for camera {camera_id}: {e}")
        
        self._camera_tasks.clear()
        logger.info("✅ All detection loops cancelled - they will respawn with new model")
    
    async def _main_loop(self):
        """Main loop that monitors cameras"""
        while self._running:
            try:
                # Get all cameras with detection enabled
                async with AsyncSessionLocal() as db:
                    result = await db.execute(
                        select(Camera).where(Camera.detection_enabled == True)
                    )
                    cameras = result.scalars().all()
                    
                    stream_manager = get_stream_manager()
                    
                    logger.debug(f"Detection service checking {len(cameras)} cameras")
                    
                    for camera in cameras:
                        # Check if stream is running
                        handler = stream_manager.get_stream(camera.id)
                        is_connected = handler.is_connected() if handler else False
                        
                        if handler and is_connected:
                            # Start detection task if not running
                            if camera.id not in self._camera_tasks or self._camera_tasks[camera.id].done():
                                logger.info(f"🎯 Starting detection task for camera {camera.id}")
                                self._camera_tasks[camera.id] = asyncio.create_task(
                                    self._detection_loop(camera.id, camera.owner_id)
                                )
                        else:
                            # Stop detection if stream stopped
                            if camera.id in self._camera_tasks:
                                self._camera_tasks[camera.id].cancel()
                                del self._camera_tasks[camera.id]
                
                await asyncio.sleep(5)  # Check every 5 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Detection service error: {e}")
                await asyncio.sleep(5)
    
    async def _detection_loop(self, camera_id: int, user_id: int):
        """Main detection loop for a camera using V-JEPA 2"""
        stream_manager = get_stream_manager()
        
        # Get V-JEPA 2 service
        vjepa2_service = await get_vjepa2_service()
        
        # Get user's detection settings
        user_settings = await self._get_user_settings(user_id)
        model_name = user_settings.get("vjepa2_model", "vjepa2-large") if user_settings else "vjepa2-large"
        device = user_settings.get("device", "cuda") if user_settings else "cuda"
        
        logger.info(f"📷 Camera {camera_id}: Starting V-JEPA 2 detection with model={model_name}")
        
        # Initialize V-JEPA 2 if not already
        if not vjepa2_service.initialized:
            await vjepa2_service.initialize(model_name=model_name, device=device)
        
        frame_count = 0
        null_frame_count = 0
        
        while self._running:
            try:
                handler = stream_manager.get_stream(camera_id)
                if not handler or not handler.is_connected():
                    logger.warning(f"Camera {camera_id}: Stream disconnected, stopping detection")
                    break
                
                # Get frame from stream
                frame = await handler.get_frame_async(timeout=0.5)
                if frame is None:
                    null_frame_count += 1
                    if null_frame_count % 100 == 0:
                        logger.debug(f"Camera {camera_id}: No frames available ({null_frame_count} null frames)")
                    await asyncio.sleep(0.1)
                    continue
                
                null_frame_count = 0
                frame_count += 1
                
                # Process frame with V-JEPA 2 (handles buffering internally)
                result = await vjepa2_service.process_frame(camera_id, frame)
                
                if result is None:
                    # Buffer not ready yet, continue collecting frames
                    continue
                
                detections = result.get("detections", [])
                
                if not detections:
                    continue
                
                logger.info(f"🎬 Camera {camera_id}: V-JEPA 2 detected {len(detections)} activities")
                
                # Process detections and create events
                await self._process_detections(
                    camera_id, user_id, frame, detections, vjepa2_service
                )
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Detection error for camera {camera_id}: {e}")
                await asyncio.sleep(1)
        
        # Clear buffer when loop ends
        vjepa2_service.clear_buffer(camera_id)
        logger.info(f"Stopped detection loop for camera {camera_id}")
    
    def _is_cache_valid(self, user_id: int) -> bool:
        """Check if settings cache is still valid"""
        if user_id not in self._settings_cache_time:
            return False
        cache_age = (datetime.now() - self._settings_cache_time[user_id]).total_seconds()
        return cache_age < self._settings_cache_ttl
    
    def _invalidate_cache(self, user_id: int = None):
        """Invalidate settings cache for a user or all users"""
        if user_id:
            self._settings_cache.pop(user_id, None)
            self._settings_cache_time.pop(user_id, None)
        else:
            self._settings_cache.clear()
            self._settings_cache_time.clear()
    
    async def _get_user_settings(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user's detection settings from database with caching"""
        # Check cache first
        if self._is_cache_valid(user_id) and user_id in self._settings_cache:
            return self._settings_cache.get(user_id)
        
        try:
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(UserSettings).where(UserSettings.user_id == user_id)
                )
                user_settings = result.scalar_one_or_none()
                
                if user_settings:
                    settings_dict = {
                        "vjepa2_model": getattr(user_settings, 'vjepa2_model', 'vjepa2-large'),
                        "device": getattr(user_settings, 'detection_device', 'cuda'),
                        "buffer_size": getattr(user_settings, 'vjepa2_buffer_size', 64),
                        "sample_rate": getattr(user_settings, 'vjepa2_sample_rate', 4),
                    }
                    # Update cache
                    self._settings_cache[user_id] = settings_dict
                    self._settings_cache_time[user_id] = datetime.now()
                    return settings_dict
                return None
        except Exception as e:
            logger.error(f"Failed to get user settings for user {user_id}: {e}")
            return None
    
    async def _process_detections(
        self, 
        camera_id: int, 
        user_id: int,
        frame: np.ndarray,
        detections: List[dict],
        vjepa2_service: VJEPA2Service
    ):
        """Process V-JEPA 2 detections and create events"""
        now = datetime.now()
        
        for detection in detections:
            activity = detection.get("class", "unknown")
            cooldown_key = f"{camera_id}:{activity}"
            
            # Check cooldown
            last_time = self._last_event_time.get(cooldown_key)
            if last_time and (now - last_time).seconds < self._event_cooldown:
                continue
            
            # Update cooldown
            self._last_event_time[cooldown_key] = now
            
            # Get event type and severity from detection
            event_type = detection.get("event_type")
            if event_type is None:
                event_type = EventType.motion_detected
            
            severity = detection.get("severity", EventSeverity.low)
            confidence = detection.get("confidence", 0.5)
            description = detection.get("description", f"Activity detected: {activity}")
            
            logger.info(f"🔔 Creating event: type={event_type.value}, severity={severity.value}, activity={activity}")
            
            # Save frame
            frame_path = await self._save_frame(camera_id, frame)
            
            # Create event in database
            try:
                async with AsyncSessionLocal() as db:
                    event = Event(
                        event_type=event_type,
                        severity=severity,
                        detected_objects=[{
                            "class": activity,
                            "confidence": confidence,
                            "bbox": detection.get("bbox")
                        }],
                        confidence_score=confidence,
                        frame_path=frame_path,
                        thumbnail_path=frame_path,
                        summary=description,
                        detection_metadata={
                            "model": "vjepa2",
                            "activity": activity,
                        },
                        timestamp=now,
                        camera_id=camera_id,
                        user_id=user_id
                    )
                    db.add(event)
                    await db.commit()
                    await db.refresh(event)
                    
                    logger.info(f"✅ Event created: ID={event.id}, {event_type.value} - {activity}")
                    
                    # Send notification
                    asyncio.create_task(
                        self._send_notification(event.id, description, severity, user_id, camera_id)
                    )
                    
            except Exception as e:
                logger.error(f"❌ Failed to create event: {e}", exc_info=True)
    
    async def _save_frame(self, camera_id: int, frame: np.ndarray) -> str:
        """Save frame to disk"""
        # Create filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"cam{camera_id}_{timestamp}_{uuid.uuid4().hex[:8]}.jpg"
        
        # Use absolute path
        frames_dir = Path(settings.frames_storage_path).resolve()
        frames_dir.mkdir(parents=True, exist_ok=True)
        filepath = frames_dir / filename
        
        # Save frame
        cv2.imwrite(str(filepath), frame)
        
        return str(filepath)
    
    async def _send_notification(
        self,
        event_id: int,
        summary: str,
        severity: EventSeverity,
        user_id: int,
        camera_id: int
    ):
        """Send notification for event"""
        try:
            # Get camera name
            camera_name = f"Camera {camera_id}"
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(Camera).where(Camera.id == camera_id)
                )
                camera = result.scalar_one_or_none()
                if camera:
                    camera_name = camera.name or camera_name
            
            # Send notification
            await send_event_notification(
                event_id=event_id,
                camera_name=camera_name,
                summary=summary,
                severity=severity.value,
                user_id=user_id
            )
        except Exception as e:
            logger.error(f"Failed to send notification for event {event_id}: {e}")
    
    def stop_all(self):
        """Stop all detection tasks"""
        pass


# Global singleton instance
detection_service = DetectionService()

# Alternative async getter
_detection_service: Optional[DetectionService] = None


async def get_detection_service() -> DetectionService:
    """Async getter for detection service (returns the global singleton)"""
    return detection_service
