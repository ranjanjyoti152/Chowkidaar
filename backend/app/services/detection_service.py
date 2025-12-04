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
        self._last_vlm_scan: Dict[int, datetime] = {}  # camera_id -> last VLM scan time
        self._vlm_scan_interval = 30  # VLM safety scan every 30 seconds
    
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
                
                # Periodic VLM safety scan (even if YOLO missed something)
                # Get scan interval from user settings
                vlm_settings = await self._get_vlm_settings(user_id)
                scan_interval = vlm_settings.get("safety_scan_interval", 30) if vlm_settings else 30
                
                now = datetime.now()
                last_scan = self._last_vlm_scan.get(camera_id)
                if not last_scan or (now - last_scan).total_seconds() >= scan_interval:
                    self._last_vlm_scan[camera_id] = now
                    # Run VLM safety scan in background (don't block detection loop)
                    asyncio.create_task(self._vlm_safety_scan(camera_id, user_id, frame))
                
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
                        "summarize_delay": user_settings.summarize_delay,
                        "safety_scan_enabled": getattr(user_settings, 'vlm_safety_scan_enabled', True),
                        "safety_scan_interval": getattr(user_settings, 'vlm_safety_scan_interval', 30)
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
        now = datetime.now()
        
        # Group all detections of same class together
        class_detections = {}
        for detection in detections:
            class_name = detection["class_name"]
            if class_name not in class_detections:
                class_detections[class_name] = []
            class_detections[class_name].append(detection)
        
        # Create one event per class with all detections of that class
        for class_name, class_dets in class_detections.items():
            cooldown_key = f"{camera_id}:{class_name}"
            
            # Check cooldown for this class on this camera
            last_time = self._last_event_time.get(cooldown_key)
            if last_time and (now - last_time).seconds < self._event_cooldown:
                continue  # Skip - still in cooldown
            
            # Update cooldown
            self._last_event_time[cooldown_key] = now
            
            # Use highest confidence detection for primary info
            primary_detection = max(class_dets, key=lambda x: x["confidence"])
            
            # Determine event type and severity
            event_type = self._get_event_type(class_dets)
            severity = self._get_severity(class_dets)
            
            # Count of this class
            count = len(class_dets)
            logger.info(f"🔔 Creating event: type={event_type.value}, severity={severity.value}, class={class_name}, count={count}")
            
            # Save frame with ALL detections of this class drawn
            frame_path = await self._save_frame(camera_id, frame, class_dets, detector)
            logger.debug(f"Frame saved to: {frame_path}")
            
            # Create event in database with ALL detected objects
            try:
                async with AsyncSessionLocal() as db:
                    event = Event(
                        event_type=event_type,
                        severity=severity,
                        detected_objects=[{
                            "class": d["class_name"],
                            "confidence": d["confidence"],
                            "bbox": d["bbox"]
                        } for d in class_dets],
                        confidence_score=primary_detection["confidence"],
                        frame_path=frame_path,
                        thumbnail_path=frame_path,
                        detection_metadata={
                            "model": "yolov8",
                            "class": class_name,
                            "count": count,
                            "all_confidences": [d["confidence"] for d in class_dets]
                        },
                        timestamp=now,
                        camera_id=camera_id,
                        user_id=user_id
                    )
                    db.add(event)
                    await db.commit()
                    await db.refresh(event)
                    
                    logger.info(f"✅ Event created: ID={event.id}, {event_type.value} ({count}x {class_name}) on camera {camera_id}")
                    
                    # Generate summary with VLM and then send notification
                    asyncio.create_task(
                        self._generate_summary_and_notify(event.id, frame, class_dets, user_id)
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
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
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
            
            # Create detailed detection info with counts
            class_counts = {}
            for d in detections:
                cn = d["class_name"]
                if cn not in class_counts:
                    class_counts[cn] = {"count": 0, "confidences": []}
                class_counts[cn]["count"] += 1
                class_counts[cn]["confidences"].append(d["confidence"])
            
            # Format: "3x person (85%, 78%, 72%), 2x car (91%, 88%)"
            detection_summary = ", ".join([
                f"{info['count']}x {cls} ({', '.join([f'{c:.0%}' for c in info['confidences']])})"
                for cls, info in class_counts.items()
            ])
            
            total_objects = len(detections)
            current_time = datetime.now()
            hour = current_time.hour
            
            # More detailed time context
            if hour >= 0 and hour < 5:
                time_context = "late night (most suspicious time)"
            elif hour >= 5 and hour < 7:
                time_context = "early morning"
            elif hour >= 7 and hour < 12:
                time_context = "morning"
            elif hour >= 12 and hour < 17:
                time_context = "afternoon"
            elif hour >= 17 and hour < 20:
                time_context = "evening"
            elif hour >= 20 and hour < 22:
                time_context = "night"
            else:
                time_context = "late night (suspicious time)"
            
            # Combined prompt for summary AND severity analysis
            prompt = f"""You are an expert AI security analyst for a home/office surveillance system called "Chowkidaar".

CONTEXT:
- Detected: {detection_summary}
- Total Objects: {total_objects}
- Time: {time_context} ({current_time.strftime('%I:%M %p')})
- Location: Security camera feed

IMPORTANT RULES FOR ANALYSIS:
1. Look at the ACTUAL image carefully, not just the detection labels
2. A "person" detection could be: a real person, a poster, TV screen, mannequin, or misdetection
3. Objects like chairs, TVs, laptops are NOT threats - mark as LOW severity
4. Only mark HIGH/CRITICAL if you see ACTUAL threatening activity
5. MULTIPLE people/vehicles = mention the COUNT in summary
5. Be conservative - false alarms are worse than missed low-priority events

THREAT LEVEL GUIDELINES:
- CRITICAL: Active fire/smoke, weapon visible, physical violence, break-in in progress, child in danger
- HIGH: Unknown person at night near entry points, someone hiding/lurking, running away with items, forced entry attempt
- MEDIUM: Unknown person during day, unusual vehicle, person looking around suspiciously, loitering
- LOW: Empty scene, furniture/objects only, known safe activity, pets, regular movement, false detection

EVENT TYPE (choose ONE):
- intrusion: Break-in attempt, unauthorized entry, climbing fence/wall
- theft_attempt: Stealing items, taking packages, robbery
- suspicious: Lurking, hiding, casing the property, unusual behavior
- loitering: Standing around too long without purpose
- delivery: Courier, postman, food delivery with uniform/package
- visitor: Normal person approaching door, guest arriving
- package_left: Package/parcel placed at door
- person_detected: Person visible but normal activity
- vehicle_detected: Car/bike movement
- animal_detected: Pet or animal
- motion_detected: No person/vehicle, just objects or empty scene

Analyze the image and respond in this EXACT format (no markdown):
SUMMARY: [2-3 sentence description of what you actually see in the image]
THREAT_LEVEL: [low/medium/high/critical]
EVENT_TYPE: [one type from above]
THREAT_REASON: [Brief reason for your threat assessment]"""
            
            # Generate analysis using describe_frame
            response = await vlm.describe_frame(frame, detections, prompt)
            
            if response:
                # Parse the response - handle multi-line values
                summary = ""
                threat_level = "low"
                event_type_str = ""
                threat_reason = ""
                
                # Use regex-like parsing for better extraction
                response_upper = response.upper()
                response_clean = response.replace('**', '').replace('*', '')
                
                # Find SUMMARY
                if 'SUMMARY:' in response_upper:
                    start = response_upper.find('SUMMARY:') + 8
                    # Find next field or end
                    end = len(response)
                    for marker in ['THREAT_LEVEL:', 'EVENT_TYPE:', 'THREAT_REASON:']:
                        pos = response_upper.find(marker, start)
                        if pos != -1 and pos < end:
                            end = pos
                    summary = response_clean[start:end].strip()
                
                # Find THREAT_LEVEL
                if 'THREAT_LEVEL:' in response_upper:
                    start = response_upper.find('THREAT_LEVEL:') + 13
                    end = len(response)
                    for marker in ['EVENT_TYPE:', 'THREAT_REASON:', 'SUMMARY:']:
                        pos = response_upper.find(marker, start)
                        if pos != -1 and pos < end:
                            end = pos
                    level = response_clean[start:end].strip().lower().split()[0] if response_clean[start:end].strip() else 'low'
                    if level in ['low', 'medium', 'high', 'critical']:
                        threat_level = level
                
                # Find EVENT_TYPE
                if 'EVENT_TYPE:' in response_upper:
                    start = response_upper.find('EVENT_TYPE:') + 11
                    end = len(response)
                    for marker in ['THREAT_LEVEL:', 'THREAT_REASON:', 'SUMMARY:']:
                        pos = response_upper.find(marker, start)
                        if pos != -1 and pos < end:
                            end = pos
                    event_type_str = response_clean[start:end].strip().lower().split()[0] if response_clean[start:end].strip() else ''
                    # Remove any trailing punctuation
                    event_type_str = event_type_str.rstrip('.,;:')
                
                # Find THREAT_REASON
                if 'THREAT_REASON:' in response_upper:
                    start = response_upper.find('THREAT_REASON:') + 14
                    end = len(response)
                    for marker in ['SUMMARY:', 'THREAT_LEVEL:', 'EVENT_TYPE:']:
                        pos = response_upper.find(marker, start)
                        if pos != -1 and pos < end:
                            end = pos
                    threat_reason = response_clean[start:end].strip()
                
                # If parsing failed, use full response as summary
                if not summary:
                    summary = response_clean.strip()[:500]  # Limit to 500 chars
                
                logger.debug(f"VLM Response parsed - Summary: {summary[:50]}..., Level: {threat_level}, Type: {event_type_str}")
                
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
                    'motion_detected': EventType.motion_detected,
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
                        "analyzed_at": datetime.now().isoformat()
                    },
                    "summary_generated_at": datetime.now()
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
        if any(c in classes for c in ["dog", "cat", "bird", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe"]):
            return EventType.animal_detected
        
        # For all other objects (chair, tv, laptop, etc.) - just motion/object detected
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
        hour = datetime.now().hour
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
    
    async def _vlm_safety_scan(self, camera_id: int, user_id: int, frame: np.ndarray):
        """
        Periodic VLM scan to detect threats that YOLO might miss.
        This catches fire, weapons, violence, and other dangerous situations
        even if they're not in YOLO's training classes.
        """
        try:
            vlm_settings = await self._get_vlm_settings(user_id)
            if not vlm_settings:
                return  # VLM not configured
            
            # Check if safety scan is enabled
            if not vlm_settings.get("safety_scan_enabled", True):
                return  # Safety scan disabled by user
            
            vlm = await get_vlm_service()
            vlm.configure(
                base_url=vlm_settings.get("url", "http://localhost:11434"),
                vlm_model=vlm_settings.get("model", "gemma3:4b"),
                chat_model=vlm_settings.get("model", "gemma3:4b")
            )
            
            current_time = datetime.now()
            hour = current_time.hour
            
            if hour >= 0 and hour < 5:
                time_context = "late night (most suspicious time)"
            elif hour >= 5 and hour < 7:
                time_context = "early morning"
            elif hour >= 7 and hour < 12:
                time_context = "morning"
            elif hour >= 12 and hour < 17:
                time_context = "afternoon"
            elif hour >= 17 and hour < 20:
                time_context = "evening"
            elif hour >= 20 and hour < 22:
                time_context = "night"
            else:
                time_context = "late night"
            
            # Special prompt for VLM-only safety scan
            prompt = f"""You are a security AI analyzing a surveillance frame for dangerous situations that automated detection might miss.

TIME: {current_time.strftime('%H:%M')} ({time_context})

YOUR MISSION: Look for CRITICAL THREATS that object detection models cannot see:
1. FIRE or FLAMES anywhere in the image
2. SMOKE (even small amounts)
3. WEAPONS (guns, knives, sticks being used as weapons)
4. PHYSICAL VIOLENCE or FIGHTING
5. BREAK-IN or forced entry in progress
6. SUSPICIOUS PACKAGES that could be dangerous
7. FLOODING or water damage
8. FALLEN/INJURED person
9. CHILD in danger or unsupervised in dangerous area
10. Any other EMERGENCY SITUATION

BE VERY CAREFUL:
- Only report REAL threats you can clearly see
- False alarms waste resources and reduce trust
- Normal activities are NOT threats
- If scene looks safe, say "SAFE"

Respond in this EXACT format:
THREAT_DETECTED: [yes/no]
THREAT_TYPE: [fire/smoke/weapon/violence/intrusion/suspicious_package/flooding/medical/child_danger/other/none]
THREAT_LEVEL: [critical/high/medium/low/safe]
DESCRIPTION: [What you see - be specific about location in frame and what's happening]"""

            # Use describe_frame with empty detections list
            response = await vlm.describe_frame(frame, [], prompt)
            
            if not response:
                return
            
            logger.debug(f"VLM Safety Scan camera {camera_id}: {response[:100]}...")
            
            # Parse response
            response_upper = response.upper()
            response_clean = response.replace('**', '').replace('*', '')
            
            threat_detected = False
            threat_type = "none"
            threat_level = "safe"
            description = ""
            
            # Parse THREAT_DETECTED
            if 'THREAT_DETECTED:' in response_upper:
                start = response_upper.find('THREAT_DETECTED:') + 16
                end = min(start + 20, len(response))
                answer = response_clean[start:end].strip().lower()
                threat_detected = 'yes' in answer or 'true' in answer
            
            # Parse THREAT_TYPE
            if 'THREAT_TYPE:' in response_upper:
                start = response_upper.find('THREAT_TYPE:') + 12
                end = len(response)
                for marker in ['THREAT_LEVEL:', 'DESCRIPTION:', 'THREAT_DETECTED:']:
                    pos = response_upper.find(marker, start)
                    if pos != -1 and pos < end:
                        end = pos
                threat_type = response_clean[start:end].strip().lower().split()[0] if response_clean[start:end].strip() else 'none'
                threat_type = threat_type.rstrip('.,;:')
            
            # Parse THREAT_LEVEL
            if 'THREAT_LEVEL:' in response_upper:
                start = response_upper.find('THREAT_LEVEL:') + 13
                end = len(response)
                for marker in ['THREAT_TYPE:', 'DESCRIPTION:', 'THREAT_DETECTED:']:
                    pos = response_upper.find(marker, start)
                    if pos != -1 and pos < end:
                        end = pos
                level = response_clean[start:end].strip().lower().split()[0] if response_clean[start:end].strip() else 'safe'
                if level in ['critical', 'high', 'medium', 'low', 'safe']:
                    threat_level = level
            
            # Parse DESCRIPTION
            if 'DESCRIPTION:' in response_upper:
                start = response_upper.find('DESCRIPTION:') + 12
                end = len(response)
                for marker in ['THREAT_DETECTED:', 'THREAT_TYPE:', 'THREAT_LEVEL:']:
                    pos = response_upper.find(marker, start)
                    if pos != -1 and pos < end:
                        end = pos
                description = response_clean[start:end].strip()
            
            # Only create event if real threat detected
            if threat_detected and threat_level in ['critical', 'high', 'medium']:
                logger.warning(f"🚨 VLM Safety Scan detected {threat_level.upper()} threat on camera {camera_id}: {threat_type}")
                
                # Map threat type to event type
                threat_event_map = {
                    'fire': EventType.fire_detected,
                    'smoke': EventType.smoke_detected,
                    'weapon': EventType.intrusion,
                    'violence': EventType.intrusion,
                    'intrusion': EventType.intrusion,
                    'suspicious_package': EventType.suspicious,
                    'flooding': EventType.motion_detected,
                    'medical': EventType.motion_detected,
                    'child_danger': EventType.suspicious,
                }
                event_type = threat_event_map.get(threat_type, EventType.suspicious)
                
                # Map threat level to severity
                severity_map = {
                    'critical': EventSeverity.critical,
                    'high': EventSeverity.high,
                    'medium': EventSeverity.medium
                }
                severity = severity_map.get(threat_level, EventSeverity.medium)
                
                # Save frame
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                frame_filename = f"vlm_scan_{camera_id}_{timestamp}_{uuid.uuid4().hex[:8]}.jpg"
                frame_path = Path(settings.STORAGE_PATH) / "events" / frame_filename
                frame_path.parent.mkdir(parents=True, exist_ok=True)
                cv2.imwrite(str(frame_path), frame)
                
                # Create VLM-detected event
                async with AsyncSessionLocal() as db:
                    event = Event(
                        camera_id=camera_id,
                        event_type=event_type,
                        severity=severity,
                        summary=description or f"VLM detected {threat_type} threat",
                        frame_path=str(frame_path),
                        detection_metadata={
                            "source": "vlm_safety_scan",
                            "vlm_threat_type": threat_type,
                            "vlm_threat_level": threat_level,
                            "vlm_description": description,
                            "time_context": time_context,
                            "scan_time": datetime.now().isoformat()
                        },
                        summary_generated_at=datetime.now()
                    )
                    db.add(event)
                    await db.commit()
                    await db.refresh(event)
                    
                    logger.warning(f"🔥 VLM Safety Event created: ID={event.id}, Type={threat_type}, Level={threat_level}")
                    
                    # Send immediate notification for VLM-detected threats
                    await send_event_notification(event, user_id)
            else:
                logger.debug(f"VLM Safety Scan camera {camera_id}: Scene is safe")
                
        except Exception as e:
            logger.error(f"VLM Safety Scan error for camera {camera_id}: {e}")


# Global instance
_detection_service: Optional[DetectionService] = None


async def get_detection_service() -> DetectionService:
    global _detection_service
    if _detection_service is None:
        _detection_service = DetectionService()
    return _detection_service
