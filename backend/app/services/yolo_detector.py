"""
Chowkidaar NVR - YOLO Object Detection Service
"""
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import numpy as np
from datetime import datetime
from loguru import logger
from ultralytics import YOLO
import cv2

from app.core.config import settings
from app.models.event import EventType, EventSeverity


class YOLODetector:
    """YOLOv8+ Object Detection Service"""
    
    # Mapping YOLO classes to event types
    CLASS_EVENT_MAPPING = {
        "person": EventType.person_detected,
        "car": EventType.vehicle_detected,
        "truck": EventType.vehicle_detected,
        "bus": EventType.vehicle_detected,
        "motorcycle": EventType.vehicle_detected,
        "bicycle": EventType.vehicle_detected,
        "dog": EventType.animal_detected,
        "cat": EventType.animal_detected,
        "bird": EventType.animal_detected,
        "fire": EventType.fire_detected,
        "smoke": EventType.smoke_detected,
    }
    
    # Severity mapping based on detected class
    CLASS_SEVERITY_MAPPING = {
        "fire": EventSeverity.critical,
        "smoke": EventSeverity.high,
        "person": EventSeverity.medium,
        "car": EventSeverity.low,
        "truck": EventSeverity.low,
    }
    
    # Color palette for tracked objects (20 distinct colors)
    TRACK_COLORS = [
        (255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (255, 0, 255),
        (0, 255, 255), (255, 128, 0), (128, 0, 255), (0, 255, 128), (255, 0, 128),
        (128, 255, 0), (0, 128, 255), (255, 128, 128), (128, 255, 128), (128, 128, 255),
        (255, 200, 0), (200, 0, 255), (0, 200, 255), (255, 100, 100), (100, 255, 100)
    ]
    
    def __init__(self):
        self.model: Optional[YOLO] = None
        self.model_path = settings.yolo_model_path
        self.model_name = "yolov8n"
        self.confidence_threshold = settings.yolo_confidence_threshold
        self.target_classes = settings.yolo_classes_list
        self.device = "cuda"  # Default to GPU
        self.inference_stats = {
            "count": 0,
            "total_time": 0.0,
            "last_time": 0.0
        }
        self._initialized = False
        self._current_model_name = None
        # Per-camera tracker state for persistent tracking
        self._camera_trackers: Dict[int, bool] = {}  # camera_id -> tracker initialized
        self._default_tracker = "bytetrack.yaml"  # Default tracker config
    
    async def load_model(self, model_name: str, device: str = "cuda") -> bool:
        """Load a specific YOLO model by name"""
        # Skip if same model already loaded
        if self._initialized and self._current_model_name == model_name and self.device == device:
            logger.debug(f"Model {model_name} already loaded on {device}")
            return True
        
        try:
            self.device = device
            self.model_name = model_name
            
            # Build model path - check multiple locations
            # 1. Check in models directory (for custom uploaded models)
            model_path = Path(settings.models_path) / f"{model_name}.pt"
            if not model_path.exists():
                # 2. Check in base path (for built-in models like yolov8n.pt)
                model_path = Path(settings.base_path) / f"{model_name}.pt"
            if not model_path.exists():
                # 3. Try as direct path (like yolov8n.pt which ultralytics can download)
                model_path = Path(f"{model_name}.pt")
            
            if not model_path.exists() and not model_name.startswith("yolov8"):
                # For custom models, require the file to exist
                logger.error(f"Model file not found: {model_name}.pt")
                return False
            
            # For yolov8 models, ultralytics will auto-download if not found
            self.model_path = str(model_path)
            logger.info(f"🔄 Loading YOLO model: {model_name} from {model_path} on {device}")
            
            # Load model in a thread pool
            loop = asyncio.get_event_loop()
            self.model = await loop.run_in_executor(
                None,
                lambda: YOLO(str(model_path))
            )
            
            # Move to device
            if device == "cuda":
                import torch
                if torch.cuda.is_available():
                    self.model.to("cuda")
                    logger.info(f"✅ YOLO model {model_name} loaded on GPU: {torch.cuda.get_device_name(0)}")
                else:
                    self.device = "cpu"
                    logger.warning("⚠️ CUDA not available, using CPU")
            else:
                self.model.to("cpu")
                logger.info(f"✅ YOLO model {model_name} loaded on CPU")
            
            self._initialized = True
            self._current_model_name = model_name
            return True
            
        except Exception as e:
            logger.error(f"Failed to load model {model_name}: {e}")
            return False
    
    async def initialize(self, device: Optional[str] = None) -> bool:
        """Initialize the YOLO model"""
        try:
            if device:
                self.device = device
            
            logger.info(f"Loading YOLO model: {self.model_path} on device: {self.device}")
            
            # Load model in a thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            self.model = await loop.run_in_executor(
                None,
                lambda: YOLO(self.model_path)
            )
            
            # Move model to specified device
            if self.device == "cuda":
                import torch
                if torch.cuda.is_available():
                    self.model.to("cuda")
                    logger.info(f"✅ YOLO model loaded on GPU: {torch.cuda.get_device_name(0)}")
                else:
                    self.device = "cpu"
                    logger.warning("⚠️ CUDA not available, falling back to CPU")
            else:
                self.model.to("cpu")
                logger.info("YOLO model loaded on CPU")
            
            self._initialized = True
            return True
            
        except Exception as e:
            logger.error(f"Failed to load YOLO model: {e}")
            return False
    
    async def detect(
        self,
        frame: np.ndarray,
        confidence_threshold: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Perform object detection on a frame
        
        Returns:
            Dictionary containing detected objects and metadata
        """
        if not self._initialized or self.model is None:
            logger.warning("YOLO model not initialized")
            return {"objects": [], "metadata": {}}
        
        conf_threshold = confidence_threshold or self.confidence_threshold
        start_time = datetime.utcnow()
        
        try:
            # Run inference in thread pool with device specified
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None,
                lambda: self.model(frame, conf=conf_threshold, device=self.device, verbose=False)
            )
            
            # Calculate inference time
            inference_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            self._update_stats(inference_time)
            
            # Process results
            detected_objects = []
            for result in results:
                boxes = result.boxes
                if boxes is not None:
                    for i, box in enumerate(boxes):
                        class_id = int(box.cls[0])
                        class_name = result.names[class_id]
                        confidence = float(box.conf[0])
                        bbox = box.xyxy[0].tolist()  # [x1, y1, x2, y2]
                        
                        detected_objects.append({
                            "class_id": class_id,
                            "class_name": class_name,
                            "confidence": confidence,
                            "bbox": bbox,
                            "bbox_normalized": self._normalize_bbox(bbox, frame.shape)
                        })
            
            return {
                "objects": detected_objects,
                "metadata": {
                    "inference_time_ms": inference_time,
                    "frame_shape": frame.shape,
                    "model": self.model_path,
                    "confidence_threshold": conf_threshold
                }
            }
            
        except Exception as e:
            logger.error(f"Detection error: {e}")
            return {"objects": [], "metadata": {"error": str(e)}}
    
    async def track(
        self,
        frame: np.ndarray,
        camera_id: int = 0,
        confidence_threshold: Optional[float] = None,
        tracker: str = "bytetrack.yaml"
    ) -> Dict[str, Any]:
        """
        Perform object detection with tracking on a frame.
        Uses ByteTrack or BoT-SORT for persistent object IDs across frames.
        
        Args:
            frame: Input image as numpy array
            camera_id: Camera ID for per-camera tracker state
            confidence_threshold: Optional confidence threshold override
            tracker: Tracker config file (bytetrack.yaml or botsort.yaml)
        
        Returns:
            Dictionary containing tracked objects with track_id and metadata
        """
        if not self._initialized or self.model is None:
            logger.warning("YOLO model not initialized")
            return {"objects": [], "metadata": {}}
        
        conf_threshold = confidence_threshold or self.confidence_threshold
        start_time = datetime.utcnow()
        
        # Check if this is a new camera needing tracker initialization
        is_new_camera = camera_id not in self._camera_trackers
        if is_new_camera:
            self._camera_trackers[camera_id] = True
            logger.info(f"📍 Initialized tracker for camera {camera_id} using {tracker}")
        
        try:
            # Run tracking inference in thread pool
            # persist=True maintains tracking state across calls for same camera
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None,
                lambda: self.model.track(
                    frame,
                    conf=conf_threshold,
                    device=self.device,
                    tracker=tracker,
                    persist=True,
                    verbose=False
                )
            )
            
            # Calculate inference time
            inference_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            self._update_stats(inference_time)
            
            # Process results with track IDs
            tracked_objects = []
            for result in results:
                boxes = result.boxes
                if boxes is not None:
                    for i, box in enumerate(boxes):
                        class_id = int(box.cls[0])
                        class_name = result.names[class_id]
                        confidence = float(box.conf[0])
                        bbox = box.xyxy[0].tolist()  # [x1, y1, x2, y2]
                        
                        # Get track ID if available
                        track_id = None
                        if box.id is not None:
                            track_id = int(box.id[0])
                        
                        tracked_objects.append({
                            "class_id": class_id,
                            "class_name": class_name,
                            "confidence": confidence,
                            "bbox": bbox,
                            "bbox_normalized": self._normalize_bbox(bbox, frame.shape),
                            "track_id": track_id
                        })
            
            return {
                "objects": tracked_objects,
                "metadata": {
                    "inference_time_ms": inference_time,
                    "frame_shape": frame.shape,
                    "model": self.model_path,
                    "confidence_threshold": conf_threshold,
                    "tracker": tracker,
                    "camera_id": camera_id,
                    "tracking_enabled": True
                }
            }
            
        except Exception as e:
            logger.error(f"Tracking error: {e}")
            return {"objects": [], "metadata": {"error": str(e)}}
    
    def reset_tracker(self, camera_id: Optional[int] = None):
        """
        Reset tracker state for a camera or all cameras.
        Call this when a camera reconnects or stream restarts.
        
        Args:
            camera_id: Specific camera to reset, or None for all cameras
        """
        if camera_id is not None:
            if camera_id in self._camera_trackers:
                del self._camera_trackers[camera_id]
                logger.info(f"🔄 Reset tracker for camera {camera_id}")
        else:
            self._camera_trackers.clear()
            logger.info("🔄 Reset all camera trackers")
    
    def _get_track_color(self, track_id: Optional[int]) -> Tuple[int, int, int]:
        """Get a unique color for a track ID"""
        if track_id is None:
            return (0, 255, 255)  # Default yellow for untracked
        return self.TRACK_COLORS[track_id % len(self.TRACK_COLORS)]
    
    def _normalize_bbox(
        self,
        bbox: List[float],
        frame_shape: Tuple[int, ...]
    ) -> List[float]:
        """Normalize bounding box to 0-1 range"""
        h, w = frame_shape[:2]
        return [
            bbox[0] / w,
            bbox[1] / h,
            bbox[2] / w,
            bbox[3] / h
        ]
    
    def _update_stats(self, inference_time: float):
        """Update inference statistics"""
        self.inference_stats["count"] += 1
        self.inference_stats["total_time"] += inference_time
        self.inference_stats["last_time"] = inference_time
    
    def get_stats(self) -> Dict[str, Any]:
        """Get inference statistics"""
        count = self.inference_stats["count"]
        avg_time = (
            self.inference_stats["total_time"] / count
            if count > 0 else 0
        )
        
        # Get GPU info if using CUDA
        gpu_info = None
        if self.device == "cuda":
            try:
                import torch
                if torch.cuda.is_available():
                    gpu_info = {
                        "name": torch.cuda.get_device_name(0),
                        "memory_allocated": f"{torch.cuda.memory_allocated(0) / 1024**2:.1f} MB",
                        "memory_reserved": f"{torch.cuda.memory_reserved(0) / 1024**2:.1f} MB"
                    }
            except:
                pass
        
        return {
            "model_name": self.model_path,
            "device": self.device,
            "gpu_info": gpu_info,
            "inference_count": count,
            "average_inference_time_ms": avg_time,
            "last_inference_time_ms": self.inference_stats["last_time"],
            "fps": 1000 / avg_time if avg_time > 0 else 0
        }
    
    def filter_detections(
        self,
        detections: List[Dict[str, Any]],
        target_classes: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Filter detections by target classes"""
        classes = target_classes or self.target_classes
        return [
            d for d in detections
            if d["class_name"].lower() in [c.lower() for c in classes]
        ]
    
    def get_event_type(self, class_name: str) -> EventType:
        """Get event type for a detected class"""
        return self.CLASS_EVENT_MAPPING.get(
            class_name.lower(),
            EventType.CUSTOM
        )
    
    def get_severity(self, class_name: str) -> EventSeverity:
        """Get severity for a detected class"""
        return self.CLASS_SEVERITY_MAPPING.get(
            class_name.lower(),
            EventSeverity.LOW
        )
    
    def draw_detections(
        self,
        frame: np.ndarray,
        detections: List[Dict[str, Any]],
        color: Optional[Tuple[int, int, int]] = None,
        use_track_colors: bool = True
    ) -> np.ndarray:
        """
        Draw detection boxes on frame with optional track-based coloring.
        
        Args:
            frame: Input frame to annotate
            detections: List of detection dictionaries
            color: Override color for all boxes (ignores track colors)
            use_track_colors: If True and no color override, use unique colors per track_id
        """
        annotated = frame.copy()
        
        for det in detections:
            bbox = det["bbox"]
            x1, y1, x2, y2 = map(int, bbox)
            
            # Determine box color
            if color is not None:
                box_color = color
            elif use_track_colors and "track_id" in det:
                box_color = self._get_track_color(det.get("track_id"))
            else:
                box_color = (0, 255, 255)  # Default yellow
            
            # Draw box with thicker border for better visibility
            cv2.rectangle(annotated, (x1, y1), (x2, y2), box_color, 2)
            
            # Build label with track ID if available
            track_id = det.get("track_id")
            if track_id is not None:
                label = f"{det['class_name']} #{track_id}: {det['confidence']:.2f}"
            else:
                label = f"{det['class_name']}: {det['confidence']:.2f}"
            
            # Calculate label background size for better readability
            (label_w, label_h), baseline = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2
            )
            
            # Draw label background
            cv2.rectangle(
                annotated,
                (x1, y1 - label_h - 10),
                (x1 + label_w + 4, y1),
                box_color,
                -1  # Filled
            )
            
            # Draw label text (black text on colored background)
            cv2.putText(
                annotated,
                label,
                (x1 + 2, y1 - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 0, 0),  # Black text
                2
            )
        
        return annotated
    
    async def shutdown(self):
        """Cleanup resources"""
        self.model = None
        self._initialized = False
        logger.info("YOLO detector shutdown complete")


# Global detector instance
detector = YOLODetector()


async def get_detector() -> YOLODetector:
    """Get the YOLO detector instance"""
    if not detector._initialized:
        await detector.initialize()
    return detector
