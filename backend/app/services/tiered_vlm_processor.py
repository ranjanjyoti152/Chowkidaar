"""
Chowkidaar NVR - Tiered VLM Processor
Optimizes VLM usage based on event severity and detection patterns.

Strategy:
- SKIP (Low severity): Template-based summaries (no VLM call)
- FAST (Medium severity): Fast local model (SmolVLM, Moondream)
- BEST (High/Critical): Best available provider (Gemini, GPT-4)
"""
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from loguru import logger
import numpy as np

from app.models.event import EventSeverity, EventType


class TieredVLMProcessor:
    """
    Tiered VLM processing strategy to reduce inference costs.
    
    Strategy:
    - LOW: Template-based summaries (no VLM call)
    - MEDIUM: Fast local model (SmolVLM, small Ollama)
    - HIGH/CRITICAL: Best available provider (Gemini, GPT-4)
    
    Features:
    - Event batching for low-priority items
    - Perceptual hash caching (same scene = reuse summary)
    - Configurable tier thresholds
    """
    
    # Detection classes that warrant different severity tiers
    HIGH_SEVERITY_CLASSES = {
        'fire', 'smoke', 'weapon', 'knife', 'gun', 'fight', 'violence',
        'explosion', 'crash', 'accident', 'blood', 'fall', 'collapsed'
    }
    
    MEDIUM_SEVERITY_CLASSES = {
        'person', 'intruder', 'suspicious', 'unknown', 'package',
        'vehicle', 'car', 'truck', 'motorcycle'
    }
    
    LOW_SEVERITY_CLASSES = {
        'dog', 'cat', 'bird', 'animal', 'chair', 'laptop', 'tv',
        'bottle', 'cup', 'book', 'backpack', 'umbrella', 'handbag'
    }
    
    def __init__(self):
        self._batch_queue: List[Dict[str, Any]] = []
        self._batch_lock = asyncio.Lock()
        self._batch_size = 10
        self._batch_timeout = 5.0  # seconds
        
    def should_skip_vlm(
        self, 
        detections: List[Dict], 
        preliminary_severity: str = "low"
    ) -> Tuple[bool, Optional[str]]:
        """
        Determine if we should skip VLM and use template summary.
        
        Returns:
            (should_skip, template_summary or None)
        """
        if not detections:
            return True, None
        
        # Get primary detection class
        classes = [d.get("class_name", "").lower() for d in detections]
        primary_class = max(set(classes), key=classes.count)
        
        # Check if any high-severity class present
        if any(c in self.HIGH_SEVERITY_CLASSES for c in classes):
            return False, None  # Always use VLM for high severity
        
        # Skip VLM for routine low-severity detections
        if preliminary_severity == "low":
            # Check if all detections are low-severity classes
            if all(c in self.LOW_SEVERITY_CLASSES for c in classes):
                template = self._generate_template_summary(detections, primary_class)
                return True, template
        
        return False, None
    
    def _generate_template_summary(
        self, 
        detections: List[Dict], 
        primary_class: str
    ) -> str:
        """Generate a template-based summary without VLM."""
        count = len(detections)
        confidence = max(d.get("confidence", 0) for d in detections)
        
        templates = {
            "person": f"{count} person(s) detected with {confidence:.0%} confidence. Normal activity observed.",
            "car": f"{count} vehicle(s) detected with {confidence:.0%} confidence. Normal traffic.",
            "truck": f"{count} truck(s) detected with {confidence:.0%} confidence. Normal traffic.",
            "dog": f"Pet activity: {count} dog(s) detected with {confidence:.0%} confidence.",
            "cat": f"Pet activity: {count} cat(s) detected with {confidence:.0%} confidence.",
            "bird": f"Wildlife: {count} bird(s) detected with {confidence:.0%} confidence.",
            "chair": f"Object detected: {count} chair(s) in frame.",
            "laptop": f"Object detected: {count} laptop(s) in frame.",
            "default": f"{count} {primary_class}(s) detected with {confidence:.0%} confidence."
        }
        
        return templates.get(primary_class, templates["default"])
    
    def estimate_severity_from_detections(
        self, 
        detections: List[Dict],
        hour: int = None
    ) -> str:
        """
        Pre-estimate severity based on detection classes before VLM.
        This helps decide the VLM tier to use.
        """
        if not detections:
            return "low"
        
        classes = [d.get("class_name", "").lower() for d in detections]
        
        # Critical classes
        if any(c in self.HIGH_SEVERITY_CLASSES for c in classes):
            return "high"
        
        # Time-based severity boost
        if hour is not None:
            # Late night detections are more concerning
            if "person" in classes and (hour >= 23 or hour < 5):
                return "high"
            if "person" in classes and (hour >= 21 or hour < 7):
                return "medium"
        
        # Medium severity for people/vehicles
        if any(c in self.MEDIUM_SEVERITY_CLASSES for c in classes):
            return "medium"
        
        return "low"
    
    def get_vlm_tier(self, severity: str) -> str:
        """
        Get the VLM tier to use based on severity.
        
        Returns:
            'skip' - Use template, no VLM
            'fast' - Use fast local model
            'best' - Use best available provider
        """
        tier_map = {
            "low": "skip",
            "medium": "fast",
            "high": "best",
            "critical": "best"
        }
        return tier_map.get(severity, "fast")
    
    async def queue_for_batch(self, event_data: Dict[str, Any]) -> bool:
        """
        Queue a low-priority event for batch processing.
        Returns True if queued, False if batch is full and should be processed.
        """
        async with self._batch_lock:
            self._batch_queue.append(event_data)
            return len(self._batch_queue) < self._batch_size
    
    async def get_batch(self) -> List[Dict[str, Any]]:
        """Get and clear the current batch queue."""
        async with self._batch_lock:
            batch = self._batch_queue.copy()
            self._batch_queue.clear()
            return batch
    
    def get_batch_size(self) -> int:
        """Get current batch queue size."""
        return len(self._batch_queue)


# Security-aware prompts for different scenarios
SECURITY_PROMPTS = {
    "surveillance": """You are a certified security camera monitoring system. 
Your job is to provide accurate, factual descriptions of surveillance footage 
for legitimate security purposes. Describe what you observe objectively.

DETECTED: {detections}
TIME: {time_context}
CAMERA: {camera_name}

Provide a brief, professional summary of the scene.""",

    "incident_report": """Generate a professional incident report based on the 
surveillance footage. Include: persons present, actions observed, 
objects visible, and any notable activities. This is for authorized 
security logging purposes.

DETECTED: {detections}
TIME: {time_context}

Format:
SUMMARY: [Description]
THREAT_LEVEL: [low/medium/high/critical]
EVENT_TYPE: [person_detected/vehicle_detected/suspicious/etc]""",

    "factual_only": """Describe the contents of this security camera frame. 
List all visible: people, vehicles, objects, and actions. 
Do not make judgments, just describe factually.

Objects detected: {detections}"""
}


def get_security_prompt(severity: str) -> str:
    """Get the appropriate security prompt based on severity tier."""
    if severity in ["high", "critical"]:
        return SECURITY_PROMPTS["incident_report"]
    elif severity == "medium":
        return SECURITY_PROMPTS["surveillance"]
    else:
        return SECURITY_PROMPTS["factual_only"]


# Singleton instance
_tiered_processor: Optional[TieredVLMProcessor] = None


def get_tiered_vlm_processor() -> TieredVLMProcessor:
    """Get or create the singleton tiered VLM processor."""
    global _tiered_processor
    if _tiered_processor is None:
        _tiered_processor = TieredVLMProcessor()
    return _tiered_processor
