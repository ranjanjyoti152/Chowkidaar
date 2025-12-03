"""
Chowkidaar NVR - Background Detection Service
Handles automatic event creation from detections
"""
import asyncio
from typing import Dict, Optional, List, Set
from datetime import datetime, timedelta
from loguru import logger
import cv2
import numpy as np
from pathlib import Path
import uuid

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.services.yolo_detector import get_detector
from app.services.stream_handler import get_stream_manager
from app.services.ollama_vlm import get_vlm_service
from app.models.event import Event, EventType, EventSeverity
from app.models.camera import Camera


class DetectionService:
    """Background service for detection and event creation"""
    
    def __init__(self):
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._camera_tasks: Dict[int, asyncio.Task] = {}
        self._last_event_time: Dict[str, datetime] = {}  # "camera_id:class" -> last time
        self._event_cooldown = 10  # seconds between same class events per camera
    
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
    
    async def _main_loop(self):
        """Main loop that monitors cameras"""
        while self._running:
            try:
                # Get all cameras with detection enabled
                async with AsyncSessionLocal() as db:
                    from sqlalchemy import select
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
                        logger.debug(f"Camera {camera.id}: handler={handler is not None}, connected={is_connected}")
                        
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
        """Main detection loop for a camera"""
        detector = await get_detector()
        stream_manager = get_stream_manager()
        
        frame_count = 0
        null_frame_count = 0
        logger.info(f"🔍 Started detection loop for camera {camera_id}")
        
        while self._running:
            try:
                handler = stream_manager.get_stream(camera_id)
                if not handler or not handler.is_connected():
                    logger.warning(f"Camera {camera_id}: Stream disconnected, stopping detection")
                    break  # Exit if stream stopped
                
                # Use async get_frame for better async handling
                frame = await handler.get_frame_async(timeout=0.5)
                if frame is None:
                    null_frame_count += 1
                    if null_frame_count % 100 == 0:
                        logger.debug(f"Camera {camera_id}: No frames available ({null_frame_count} null frames)")
                    await asyncio.sleep(0.1)
                    continue
                
                null_frame_count = 0
                frame_count += 1
                
                # Run detection every 30th frame (roughly every 2 seconds at 15fps)
                if frame_count % 30 != 0:
                    await asyncio.sleep(0.033)  # ~30fps
                    continue
                
                logger.info(f"🔎 Camera {camera_id}: Running detection on frame {frame_count}")
                
                # Run detection
                detection_result = await detector.detect(frame)
                detections = detection_result.get("objects", [])
                
                logger.info(f"Camera {camera_id}: Found {len(detections)} objects")
                
                if not detections:
                    continue
                
                # Filter for significant detections (confidence > 0.5)
                significant = [d for d in detections if d["confidence"] > 0.5]
                if not significant:
                    logger.debug(f"Camera {camera_id}: No significant detections (confidence > 0.5)")
                    continue
                
                logger.info(f"📸 Camera {camera_id}: {len(significant)} significant detections: {[d['class_name'] for d in significant]}")
                
                # Check cooldown and create events
                await self._process_detections(
                    camera_id, user_id, frame, significant, detector
                )
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Detection error for camera {camera_id}: {e}")
                await asyncio.sleep(1)
        
        logger.info(f"Stopped detection loop for camera {camera_id}")
    
    async def _process_detections(
        self, 
        camera_id: int, 
        user_id: int,
        frame: np.ndarray,
        detections: List[dict],
        detector
    ):
        """Process detections and create events"""
        now = datetime.utcnow()
        
        # Group detections by class
        for detection in detections:
            class_name = detection["class_name"]
            cooldown_key = f"{camera_id}:{class_name}"
            
            # Check cooldown for this class on this camera
            last_time = self._last_event_time.get(cooldown_key)
            if last_time and (now - last_time).seconds < self._event_cooldown:
                continue  # Skip - still in cooldown
            
            # Update cooldown
            self._last_event_time[cooldown_key] = now
            
            # Determine event type and severity
            event_type = self._get_event_type([detection])
            severity = self._get_severity([detection])
            
            logger.info(f"🔔 Creating event: type={event_type.value}, severity={severity.value}, class={class_name}")
            
            # Save frame
            frame_path = await self._save_frame(camera_id, frame, [detection], detector)
            logger.debug(f"Frame saved to: {frame_path}")
            
            # Create event in database
            try:
                async with AsyncSessionLocal() as db:
                    event = Event(
                        event_type=event_type,
                        severity=severity,
                        detected_objects=[{
                            "class": detection["class_name"],
                            "confidence": detection["confidence"],
                            "bbox": detection["bbox"]
                        }],
                        confidence_score=detection["confidence"],
                        frame_path=frame_path,
                        thumbnail_path=frame_path,
                        detection_metadata={
                            "model": "yolov8n",
                            "class": class_name
                        },
                        timestamp=now,
                        camera_id=camera_id,
                        user_id=user_id
                    )
                    db.add(event)
                    await db.commit()
                    await db.refresh(event)
                    
                    logger.info(f"✅ Event created: ID={event.id}, {event_type.value} ({class_name}) on camera {camera_id}")
                    
                    # Try to generate summary with VLM (don't block)
                    asyncio.create_task(
                        self._generate_summary(event.id, frame, [detection])
                    )
                    
            except Exception as e:
                logger.error(f"❌ Failed to create event: {e}", exc_info=True)
    
    async def _save_frame(
        self, 
        camera_id: int, 
        frame: np.ndarray, 
        detections: List[dict],
        detector
    ) -> str:
        """Save frame with detections drawn"""
        # Draw detections on frame
        annotated = detector.draw_detections(frame, detections)
        
        # Create filename
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"cam{camera_id}_{timestamp}_{uuid.uuid4().hex[:8]}.jpg"
        
        # Use absolute path
        frames_dir = Path(settings.frames_storage_path).resolve()
        frames_dir.mkdir(parents=True, exist_ok=True)
        filepath = frames_dir / filename
        
        # Save frame
        cv2.imwrite(str(filepath), annotated)
        
        # Return absolute path
        return str(filepath)
    
    async def _generate_summary(
        self, 
        event_id: int, 
        frame: np.ndarray,
        detections: List[dict]
    ):
        """Generate VLM summary for event"""
        try:
            vlm = await get_vlm_service()
            
            # Create clean prompt for accurate, concise summary
            objects = ", ".join(set(d["class_name"] for d in detections))
            prompt = f"""Analyze this security camera image. Detected: {objects}.

Provide a brief 2-3 sentence factual description of what you see. 
Do NOT use markdown, bullet points, or formatting.
Do NOT add notes, disclaimers, or suggestions.
Just describe the scene simply and directly."""
            
            # Generate summary using describe_frame
            summary = await vlm.describe_frame(frame, detections, prompt)
            
            if summary:
                async with AsyncSessionLocal() as db:
                    from sqlalchemy import update
                    await db.execute(
                        update(Event)
                        .where(Event.id == event_id)
                        .values(
                            summary=summary,
                            summary_generated_at=datetime.utcnow()
                        )
                    )
                    await db.commit()
                    logger.info(f"✨ Generated summary for event {event_id}")
                    
        except Exception as e:
            logger.error(f"Failed to generate summary: {e}")
    
    def _get_event_type(self, detections: List[dict]) -> EventType:
        """Determine event type from detections"""
        classes = [d["class_name"].lower() for d in detections]
        
        if "fire" in classes:
            return EventType.fire_detected
        if "smoke" in classes:
            return EventType.smoke_detected
        if "person" in classes:
            return EventType.person_detected
        if any(c in classes for c in ["car", "truck", "bus", "motorcycle"]):
            return EventType.vehicle_detected
        if any(c in classes for c in ["dog", "cat", "bird"]):
            return EventType.animal_detected
        
        return EventType.motion_detected
    
    def _get_severity(self, detections: List[dict]) -> EventSeverity:
        """Determine severity from detections"""
        classes = [d["class_name"].lower() for d in detections]
        
        if "fire" in classes:
            return EventSeverity.critical
        if "smoke" in classes:
            return EventSeverity.high
        if "person" in classes:
            return EventSeverity.medium
        
        return EventSeverity.low
    
    async def stop_all(self):
        """Stop all detection tasks"""
        await self.stop()


# Global instance
_detection_service: Optional[DetectionService] = None


async def get_detection_service() -> DetectionService:
    global _detection_service
    if _detection_service is None:
        _detection_service = DetectionService()
    return _detection_service
