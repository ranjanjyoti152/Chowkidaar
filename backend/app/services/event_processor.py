"""
Chowkidaar NVR - Event Processing Service
"""
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path
import cv2
import numpy as np
from loguru import logger
import uuid

from app.core.config import settings
from app.services.vjepa2_service import VJEPA2Service, get_vjepa2_service
from app.services.stream_handler import StreamManager, get_stream_manager
from app.models.event import EventType, EventSeverity


class EventProcessor:
    """Processes detected events and manages event lifecycle"""
    
    def __init__(self):
        self._vjepa2_service: Optional[VJEPA2Service] = None
        self._stream_manager: Optional[StreamManager] = None
        self._running = False
        self._event_callbacks: List = []
        
        # Storage paths
        self.frames_path = Path(settings.frames_storage_path)
        self.frames_path.mkdir(parents=True, exist_ok=True)
        
        # Event cooldown to avoid duplicate events
        self._last_events: Dict[int, Dict[str, datetime]] = {}
        self._cooldown_seconds = 10
    
    async def initialize(self):
        """Initialize all required services"""
        self._vjepa2_service = await get_vjepa2_service()
        self._stream_manager = get_stream_manager()
        logger.info("Event processor initialized (using V-JEPA 2)")
    
    def add_event_callback(self, callback):
        """Add callback for new events"""
        self._event_callbacks.append(callback)
    
    async def process_frame(
        self,
        frame: np.ndarray,
        camera_id: int,
        camera_name: str,
        user_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Process a single frame for detections
        
        Returns event data if an event was detected, None otherwise
        """
        if self._vjepa2_service is None:
            return None
        
        # Process frame with V-JEPA 2 (handles buffering internally)
        result = await self._vjepa2_service.process_frame(camera_id, frame)
        
        if result is None or not result.get("detections"):
            return None
        
        detections = result["detections"]
        
        # Check cooldown
        if not self._should_create_event(camera_id, detections):
            return None
        
        # Get primary detection
        primary_detection = detections[0]  # V-JEPA 2 returns one activity at a time
        event_type = primary_detection.get("event_type") or EventType.motion_detected
        severity = primary_detection.get("severity", EventSeverity.low)
        
        # Save frame
        frame_path = await self._save_frame(frame, camera_id)
        thumbnail_path = await self._save_thumbnail(frame, camera_id)
        
        # Generate summary from activity
        activity = primary_detection.get("class", "activity")
        summary = f"Detected {activity} on {camera_name}"
        
        # Create event data
        event_data = {
            "camera_id": camera_id,
            "user_id": user_id,
            "event_type": event_type,
            "severity": severity,
            "detected_objects": {
                "objects": detections,
                "count": len(detections)
            },
            "confidence_score": primary_detection.get("confidence", 0.5),
            "detection_metadata": {
                "model": "vjepa2",
                "activity": activity
            },
            "frame_path": str(frame_path) if frame_path else None,
            "thumbnail_path": str(thumbnail_path) if thumbnail_path else None,
            "summary": summary,
            "summary_generated_at": datetime.now(),
            "timestamp": datetime.now()
        }
        
        # Update cooldown
        self._update_cooldown(camera_id, detections)
        
        # Notify callbacks
        for callback in self._event_callbacks:
            try:
                await callback(event_data)
            except Exception as e:
                logger.error(f"Event callback error: {e}")
        
        return event_data
    
    def _should_create_event(
        self,
        camera_id: int,
        detections: List[Dict]
    ) -> bool:
        """Check if we should create an event (cooldown logic)"""
        if camera_id not in self._last_events:
            return True
        
        now = datetime.now()
        camera_events = self._last_events[camera_id]
        
        for det in detections:
            class_name = det.get("class", "unknown")
            if class_name not in camera_events:
                return True
            
            elapsed = (now - camera_events[class_name]).total_seconds()
            if elapsed >= self._cooldown_seconds:
                return True
        
        return False
    
    def _update_cooldown(
        self,
        camera_id: int,
        detections: List[Dict]
    ):
        """Update cooldown timestamps"""
        if camera_id not in self._last_events:
            self._last_events[camera_id] = {}
        
        now = datetime.now()
        for det in detections:
            self._last_events[camera_id][det.get("class", "unknown")] = now
    
    async def _save_frame(
        self,
        frame: np.ndarray,
        camera_id: int
    ) -> Optional[Path]:
        """Save event frame to storage"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"camera_{camera_id}_{timestamp}_{uuid.uuid4().hex[:8]}.jpg"
            filepath = self.frames_path / filename
            
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: cv2.imwrite(str(filepath), frame)
            )
            
            return filepath
        except Exception as e:
            logger.error(f"Failed to save frame: {e}")
            return None
    
    async def _save_thumbnail(
        self,
        frame: np.ndarray,
        camera_id: int,
        size: tuple = (320, 180)
    ) -> Optional[Path]:
        """Save thumbnail version of frame"""
        try:
            # Resize
            thumbnail = cv2.resize(frame, size)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"thumb_camera_{camera_id}_{timestamp}_{uuid.uuid4().hex[:8]}.jpg"
            filepath = self.frames_path / "thumbnails"
            filepath.mkdir(exist_ok=True)
            filepath = filepath / filename
            
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: cv2.imwrite(str(filepath), thumbnail, [cv2.IMWRITE_JPEG_QUALITY, 70])
            )
            
            return filepath
        except Exception as e:
            logger.error(f"Failed to save thumbnail: {e}")
            return None


# Global event processor instance
event_processor = EventProcessor()


async def get_event_processor() -> EventProcessor:
    """Get the event processor instance"""
    if event_processor._vjepa2_service is None:
        await event_processor.initialize()
    return event_processor
