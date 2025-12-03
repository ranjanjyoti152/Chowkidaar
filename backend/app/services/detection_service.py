"""
Chowkidaar NVR - Background Detection Service
Handles automatic event creation from detections
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
from app.services.yolo_detector import get_detector
from app.services.stream_handler import get_stream_manager
from app.services.ollama_vlm import get_vlm_service
from app.services.notification_service import send_event_notification
from app.models.event import Event, EventType, EventSeverity
from app.models.camera import Camera
from app.models.settings import UserSettings


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
                    # import at top
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
        stream_manager = get_stream_manager()
        
        # Get user's detection settings
        user_settings = await self._get_user_settings(user_id)
        model_name = user_settings.get("model", "yolov8n") if user_settings else "yolov8n"
        device = user_settings.get("device", "cuda") if user_settings else "cuda"
        confidence = user_settings.get("confidence", 0.5) if user_settings else 0.5
        
        # Initialize detector with user's model
        detector = await get_detector()
        await detector.load_model(model_name, device)
        detector.confidence_threshold = confidence
        
        # Configure Ollama VLM with user's settings
        vlm_settings = await self._get_vlm_settings(user_id)
        if vlm_settings:
            vlm = await get_vlm_service()
            vlm.configure(
                base_url=vlm_settings.get("url", "http://localhost:11434"),
                vlm_model=vlm_settings.get("model", "llava"),
                chat_model=vlm_settings.get("model", "llava")
            )
            logger.info(f"VLM configured: {vlm_settings.get('url')} with model {vlm_settings.get('model')}")
        
        logger.info(f"🔍 Started detection loop for camera {camera_id} with model {model_name} on {device}")
        
        frame_count = 0
        null_frame_count = 0
        
        # Fetch user's enabled detection classes
        enabled_classes = await self._get_enabled_classes(user_id)
        logger.info(f"Camera {camera_id}: Enabled classes for user {user_id}: {enabled_classes}")
        
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
                
                # Refresh enabled classes periodically (every 100 frames)
                if frame_count % 100 == 0:
                    enabled_classes = await self._get_enabled_classes(user_id)
                    logger.debug(f"Camera {camera_id}: Refreshed enabled classes: {enabled_classes}")
                
                # Always fetch enabled classes to ensure latest settings (cached every few seconds)
                enabled_classes = await self._get_enabled_classes(user_id)
                
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
                
                # Filter by enabled classes
                if enabled_classes:
                    filtered = [d for d in significant if d["class_name"].lower() in enabled_classes]
                    if not filtered:
                        logger.debug(f"Camera {camera_id}: No detections matching enabled classes. Detected: {[d['class_name'] for d in significant]}")
                        continue
                    significant = filtered
                
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
    
    async def _get_enabled_classes(self, user_id: int) -> Set[str]:
        """Get user's enabled detection classes from settings"""
        try:
            async with AsyncSessionLocal() as db:
                # import at top
                result = await db.execute(
                    select(UserSettings).where(UserSettings.user_id == user_id)
                )
                user_settings = result.scalar_one_or_none()
                
                if user_settings and user_settings.enabled_classes:
                    # Convert to lowercase set for comparison
                    return set(c.lower() for c in user_settings.enabled_classes)
                
                # Default: all COCO classes if no settings
                return set()
        except Exception as e:
            logger.error(f"Failed to get enabled classes for user {user_id}: {e}")
            return set()
    
    async def _get_user_settings(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user's detection settings from database"""
        try:
            async with AsyncSessionLocal() as db:
                # import at top
                result = await db.execute(
                    select(UserSettings).where(UserSettings.user_id == user_id)
                )
                user_settings = result.scalar_one_or_none()
                
                if user_settings:
                    return {
                        "model": user_settings.detection_model,
                        "device": user_settings.detection_device,
                        "confidence": user_settings.detection_confidence,
                        "enabled_classes": user_settings.enabled_classes or []
                    }
                return None
        except Exception as e:
            logger.error(f"Failed to get user settings for user {user_id}: {e}")
            return None
    
    async def _get_vlm_settings(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user's VLM settings from database"""
        try:
            async with AsyncSessionLocal() as db:
                # import at top
                result = await db.execute(
                    select(UserSettings).where(UserSettings.user_id == user_id)
                )
                user_settings = result.scalar_one_or_none()
                
                if user_settings:
                    return {
                        "url": user_settings.vlm_url,
                        "model": user_settings.vlm_model,
                        "auto_summarize": user_settings.auto_summarize,
                        "summarize_delay": user_settings.summarize_delay
                    }
                return None
        except Exception as e:
            logger.error(f"Failed to get VLM settings for user {user_id}: {e}")
            return None
    
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
                    
                    # Generate summary with VLM and then send notification
                    asyncio.create_task(
                        self._generate_summary_and_notify(event.id, frame, [detection], user_id)
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
    
    async def _generate_summary_and_notify(
        self, 
        event_id: int, 
        frame: np.ndarray,
        detections: List[dict],
        user_id: int
    ):
        """Generate VLM summary, intelligent severity assessment, and send notification"""
        try:
            # Get VLM settings and configure
            vlm_settings = await self._get_vlm_settings(user_id)
            vlm = await get_vlm_service()
            
            if vlm_settings:
                vlm.configure(
                    base_url=vlm_settings.get("url", "http://localhost:11434"),
                    vlm_model=vlm_settings.get("model", "gemma3:4b"),
                    chat_model=vlm_settings.get("model", "gemma3:4b")
                )
                logger.debug(f"VLM configured for summary: {vlm_settings.get('url')} model: {vlm_settings.get('model')}")
            
            # Create clean prompt for accurate, concise summary
            objects = ", ".join(set(d["class_name"] for d in detections))
            current_time = datetime.utcnow()
            hour = current_time.hour
            time_context = "night time" if (hour >= 22 or hour < 6) else "day time" if (6 <= hour < 18) else "evening"
            
            # Combined prompt for summary AND severity analysis
            prompt = f"""You are an AI security analyst for a surveillance system.

DETECTED OBJECTS: {objects}
TIME: {time_context} ({current_time.strftime('%H:%M')})
NUMBER OF DETECTIONS: {len(detections)}

Analyze this security camera image and provide:

1. SUMMARY: A brief 2-3 sentence factual description of what you see.

2. THREAT_LEVEL: Assess the security threat level as one of: low, medium, high, critical

Consider these threat scenarios:
- CRITICAL: Fire, smoke, weapons, violent behavior, child in danger, kidnapping, theft in progress, break-in
- HIGH: Suspicious behavior at night, unknown person near doors/windows, someone running away, loitering, multiple unknown people
- MEDIUM: Unknown person during day, vehicle in unusual location, animals that could be dangerous
- LOW: Normal activity, known safe scenarios, pets, regular vehicle movement

3. EVENT_TYPE: Classify this event into ONE of these categories:
   - delivery: Person delivering package, courier, postman, food delivery
   - visitor: Known person, guest, family member visiting
   - package_left: Package or parcel left at door/property
   - suspicious: Unknown person lurking, hiding, looking around suspiciously
   - intrusion: Someone trying to break in, unauthorized entry
   - loitering: Person staying too long without clear purpose
   - theft_attempt: Someone stealing or taking items
   - person_detected: Normal person, cannot determine specific type
   - vehicle_detected: Vehicle movement
   - animal_detected: Animal or pet

4. THREAT_REASON: One sentence explaining why this threat level.

Format your response EXACTLY like this:
SUMMARY: [your summary here]
THREAT_LEVEL: [low/medium/high/critical]
EVENT_TYPE: [one of the types above]
THREAT_REASON: [reason here]

Do NOT use markdown. Be direct and factual."""
            
            # Generate analysis using describe_frame
            response = await vlm.describe_frame(frame, detections, prompt)
            
            if response:
                # Parse the response
                summary = ""
                threat_level = "low"
                event_type_str = ""
                threat_reason = ""
                
                lines = response.strip().split('\n')
                for line in lines:
                    line = line.strip()
                    if line.upper().startswith('SUMMARY:'):
                        summary = line[8:].strip()
                    elif line.upper().startswith('THREAT_LEVEL:'):
                        level = line[13:].strip().lower()
                        if level in ['low', 'medium', 'high', 'critical']:
                            threat_level = level
                    elif line.upper().startswith('EVENT_TYPE:'):
                        event_type_str = line[11:].strip().lower()
                    elif line.upper().startswith('THREAT_REASON:'):
                        threat_reason = line[14:].strip()
                
                # If parsing failed, use full response as summary
                if not summary:
                    summary = response.replace('**', '').replace('*', '').strip()
                
                # Map threat level to severity enum
                severity_map = {
                    'low': EventSeverity.low,
                    'medium': EventSeverity.medium,
                    'high': EventSeverity.high,
                    'critical': EventSeverity.critical
                }
                new_severity = severity_map.get(threat_level, EventSeverity.low)
                
                # Map LLM event type to enum
                event_type_map = {
                    'delivery': EventType.delivery,
                    'visitor': EventType.visitor,
                    'package_left': EventType.package_left,
                    'suspicious': EventType.suspicious,
                    'intrusion': EventType.intrusion,
                    'loitering': EventType.loitering,
                    'theft_attempt': EventType.theft_attempt,
                    'person_detected': EventType.person_detected,
                    'vehicle_detected': EventType.vehicle_detected,
                    'animal_detected': EventType.animal_detected,
                    'fire_detected': EventType.fire_detected,
                    'smoke_detected': EventType.smoke_detected,
                }
                new_event_type = event_type_map.get(event_type_str)
                
                # Prepare update values
                update_values = {
                    "summary": summary,
                    "severity": new_severity,
                    "detection_metadata": {
                        "ai_threat_level": threat_level,
                        "ai_event_type": event_type_str,
                        "ai_threat_reason": threat_reason,
                        "time_context": time_context,
                        "analyzed_at": datetime.utcnow().isoformat()
                    },
                    "summary_generated_at": datetime.utcnow()
                }
                
                # Update event type only if LLM classified it
                if new_event_type:
                    update_values["event_type"] = new_event_type
                
                # Update event with AI-analyzed summary, severity and event type
                async with AsyncSessionLocal() as db:
                    # import at top
                    await db.execute(
                        update(Event)
                        .where(Event.id == event_id)
                        .values(**update_values)
                    )
                    await db.commit()
                    
                    event_label = event_type_str or "unknown"
                    if threat_level in ['high', 'critical']:
                        logger.warning(f"🚨 {threat_level.upper()} THREAT Event {event_id}: {event_label} - {threat_reason}")
                    else:
                        logger.info(f"✨ Event {event_id} classified as '{event_label}' ({threat_level}) - {summary[:50]}...")
                    
                    # Send notification after summary is generated
                    # Fetch updated event for notification
                    result = await db.execute(
                        select(Event).where(Event.id == event_id)
                    )
                    updated_event = result.scalar_one_or_none()
                    if updated_event:
                        await send_event_notification(updated_event, user_id)
                    
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
        """Initial severity from detections (will be refined by AI analysis)"""
        classes = [d["class_name"].lower() for d in detections]
        
        # Basic initial severity - AI will analyze and update
        if "fire" in classes or "knife" in classes or "gun" in classes:
            return EventSeverity.critical
        if "smoke" in classes:
            return EventSeverity.high
        
        # Check time - night detections are more serious
        hour = datetime.utcnow().hour
        is_night = hour >= 22 or hour < 6
        
        if "person" in classes:
            # Multiple people or night time = higher initial severity
            person_count = sum(1 for d in detections if d["class_name"].lower() == "person")
            if is_night or person_count > 1:
                return EventSeverity.high
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
