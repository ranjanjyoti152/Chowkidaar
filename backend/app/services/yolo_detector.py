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
        "person": EventType.PERSON_DETECTED,
        "car": EventType.VEHICLE_DETECTED,
        "truck": EventType.VEHICLE_DETECTED,
        "bus": EventType.VEHICLE_DETECTED,
        "motorcycle": EventType.VEHICLE_DETECTED,
        "bicycle": EventType.VEHICLE_DETECTED,
        "dog": EventType.ANIMAL_DETECTED,
        "cat": EventType.ANIMAL_DETECTED,
        "bird": EventType.ANIMAL_DETECTED,
        "fire": EventType.FIRE_DETECTED,
        "smoke": EventType.SMOKE_DETECTED,
    }
    
    # Severity mapping based on detected class
    CLASS_SEVERITY_MAPPING = {
        "fire": EventSeverity.CRITICAL,
        "smoke": EventSeverity.HIGH,
        "person": EventSeverity.MEDIUM,
        "car": EventSeverity.LOW,
        "truck": EventSeverity.LOW,
    }
    
    def __init__(self):
        self.model: Optional[YOLO] = None
        self.model_path = settings.yolo_model_path
        self.confidence_threshold = settings.yolo_confidence_threshold
        self.target_classes = settings.yolo_classes_list
        self.inference_stats = {
            "count": 0,
            "total_time": 0.0,
            "last_time": 0.0
        }
        self._initialized = False
    
    async def initialize(self) -> bool:
        """Initialize the YOLO model"""
        try:
            logger.info(f"Loading YOLO model: {self.model_path}")
            
            # Load model in a thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            self.model = await loop.run_in_executor(
                None,
                lambda: YOLO(self.model_path)
            )
            
            self._initialized = True
            logger.info("YOLO model loaded successfully")
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
            # Run inference in thread pool
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None,
                lambda: self.model(frame, conf=conf_threshold, verbose=False)
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
        return {
            "model_name": self.model_path,
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
        color: Tuple[int, int, int] = (0, 255, 255)
    ) -> np.ndarray:
        """Draw detection boxes on frame"""
        annotated = frame.copy()
        
        for det in detections:
            bbox = det["bbox"]
            x1, y1, x2, y2 = map(int, bbox)
            
            # Draw box
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
            
            # Draw label
            label = f"{det['class_name']}: {det['confidence']:.2f}"
            cv2.putText(
                annotated,
                label,
                (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
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
