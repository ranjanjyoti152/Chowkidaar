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
from app.services.yolo_detector import YOLODetector, get_detector
from app.services.stream_handler import StreamManager, get_stream_manager
from app.services.ollama_vlm import OllamaVLMService, get_vlm_service
from app.models.event import EventType, EventSeverity


class EventProcessor:
    """Processes detected events and manages event lifecycle"""
    
    def __init__(self):
        self._detector: Optional[YOLODetector] = None
        self._vlm_service: Optional[OllamaVLMService] = None
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
        self._detector = await get_detector()
        self._vlm_service = await get_vlm_service()
        self._stream_manager = get_stream_manager()
        logger.info("Event processor initialized")
    
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
        if self._detector is None:
            return None
        
        # Run detection
        detection_result = await self._detector.detect(frame)
        
        if not detection_result["objects"]:
            return None
        
        # Filter for relevant detections
        filtered = self._detector.filter_detections(detection_result["objects"])
        
        if not filtered:
            return None
        
        # Check cooldown
        if not self._should_create_event(camera_id, filtered):
            return None
        
        # Determine primary event type (highest severity detection)
        primary_detection = self._get_primary_detection(filtered)
        event_type = self._detector.get_event_type(primary_detection["class_name"])
        severity = self._get_event_severity(filtered)
        
        # Save frame
        frame_path = await self._save_frame(frame, camera_id)
        thumbnail_path = await self._save_thumbnail(frame, camera_id)
        
        # Generate VLM summary (async)
        summary = None
        if self._vlm_service:
            try:
                summary = await self._vlm_service.generate_event_summary(
                    frame=frame,
                    event_type=event_type.value,
                    detected_objects=filtered,
                    camera_name=camera_name,
                    timestamp=datetime.now()
                )
            except Exception as e:
                logger.error(f"VLM summary error: {e}")
        
        # Create event data
        event_data = {
            "camera_id": camera_id,
            "user_id": user_id,
            "event_type": event_type,
            "severity": severity,
            "detected_objects": {
                "objects": filtered,
                "count": len(filtered)
            },
            "confidence_score": primary_detection["confidence"],
            "detection_metadata": detection_result["metadata"],
            "frame_path": str(frame_path) if frame_path else None,
            "thumbnail_path": str(thumbnail_path) if thumbnail_path else None,
            "summary": summary,
            "summary_generated_at": datetime.now() if summary else None,
            "timestamp": datetime.now()
        }
        
        # Update cooldown
        self._update_cooldown(camera_id, filtered)
        
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
            class_name = det["class_name"]
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
            self._last_events[camera_id][det["class_name"]] = now
    
    def _get_primary_detection(self, detections: List[Dict]) -> Dict:
        """Get the most significant detection"""
        # Priority: fire > smoke > person > vehicle > other
        priority = ["fire", "smoke", "person", "car", "truck"]
        
        for p in priority:
            for det in detections:
                if det["class_name"].lower() == p:
                    return det
        
        # Return highest confidence if no priority match
        return max(detections, key=lambda x: x["confidence"])
    
    def _get_event_severity(self, detections: List[Dict]) -> EventSeverity:
        """Determine overall event severity"""
        severities = [
            self._detector.get_severity(d["class_name"])
            for d in detections
        ]
        
        # Return highest severity
        severity_order = [
            EventSeverity.critical,
            EventSeverity.high,
            EventSeverity.medium,
            EventSeverity.low
        ]
        
        for sev in severity_order:
            if sev in severities:
                return sev
        
        return EventSeverity.low
    
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
    
    async def regenerate_summary(
        self,
        frame_path: str,
        event_type: str,
        detected_objects: List[Dict],
        camera_name: str,
        timestamp: datetime
    ) -> Optional[str]:
        """Regenerate VLM summary for an existing event"""
        try:
            frame = cv2.imread(frame_path)
            if frame is None:
                return None
            
            if self._vlm_service is None:
                return None
            
            return await self._vlm_service.generate_event_summary(
                frame=frame,
                event_type=event_type,
                detected_objects=detected_objects,
                camera_name=camera_name,
                timestamp=timestamp
            )
        except Exception as e:
            logger.error(f"Summary regeneration error: {e}")
            return None


# Global event processor instance
event_processor = EventProcessor()


async def get_event_processor() -> EventProcessor:
    """Get the event processor instance"""
    if event_processor._detector is None:
        await event_processor.initialize()
    return event_processor
