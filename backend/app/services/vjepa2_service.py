"""
Chowkidaar NVR - V-JEPA 2 Video Understanding Service
Meta's V-JEPA 2 for self-supervised video understanding and activity detection
"""
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import numpy as np
from datetime import datetime
from loguru import logger
import torch
from collections import deque
import cv2

from app.core.config import settings
from app.models.event import EventType, EventSeverity


class VideoBuffer:
    """Rolling buffer for video frames per camera"""
    
    def __init__(self, max_frames: int = 64, sample_rate: int = 4):
        """
        Initialize video buffer.
        
        Args:
            max_frames: Maximum frames to keep in buffer
            sample_rate: Sample every Nth frame for efficiency
        """
        self.max_frames = max_frames
        self.sample_rate = sample_rate
        self.buffers: Dict[int, deque] = {}
        self.frame_counts: Dict[int, int] = {}
        
    def add_frame(self, camera_id: int, frame: np.ndarray) -> bool:
        """
        Add frame to camera buffer.
        
        Returns:
            True if buffer is ready for processing
        """
        if camera_id not in self.buffers:
            self.buffers[camera_id] = deque(maxlen=self.max_frames)
            self.frame_counts[camera_id] = 0
            
        self.frame_counts[camera_id] += 1
        
        # Sample every Nth frame
        if self.frame_counts[camera_id] % self.sample_rate == 0:
            # Resize for V-JEPA 2 input (256x256 or 384x384)
            resized = cv2.resize(frame, (256, 256))
            self.buffers[camera_id].append(resized)
            
        return len(self.buffers[camera_id]) >= 16  # Minimum frames for analysis
    
    def get_frames(self, camera_id: int) -> Optional[List[np.ndarray]]:
        """Get current frame buffer for camera"""
        if camera_id not in self.buffers:
            return None
        return list(self.buffers[camera_id])
    
    def clear(self, camera_id: int):
        """Clear buffer for camera"""
        if camera_id in self.buffers:
            self.buffers[camera_id].clear()
            self.frame_counts[camera_id] = 0


class VJEPA2Service:
    """V-JEPA 2 Video Understanding Service"""
    
    # Available V-JEPA 2 models
    AVAILABLE_MODELS = {
        "vjepa2-large": "facebook/vjepa2-vitl-fpc64-256",
        "vjepa2-huge": "facebook/vjepa2-vith-fpc64-256",
        "vjepa2-giant": "facebook/vjepa2-vitg-fpc64-256",
        "vjepa2-giant-384": "facebook/vjepa2-vitg-fpc64-384",
    }
    
    # Activity labels for surveillance
    SURVEILLANCE_ACTIVITIES = [
        "person walking",
        "person running", 
        "person standing",
        "person entering",
        "person leaving",
        "vehicle moving",
        "vehicle parked",
        "suspicious activity",
        "normal activity",
        "no activity",
    ]
    
    # Event type mapping
    ACTIVITY_EVENT_MAPPING = {
        "person walking": EventType.person_detected,
        "person running": EventType.motion_detected,
        "person standing": EventType.person_detected,
        "person entering": EventType.person_detected,
        "person leaving": EventType.person_detected,
        "vehicle moving": EventType.vehicle_detected,
        "vehicle parked": EventType.vehicle_detected,
        "suspicious activity": EventType.object_left,
        "normal activity": EventType.motion_detected,
        "no activity": None,
    }
    
    # Severity mapping
    ACTIVITY_SEVERITY_MAPPING = {
        "person walking": EventSeverity.low,
        "person running": EventSeverity.medium,
        "person standing": EventSeverity.low,
        "person entering": EventSeverity.medium,
        "person leaving": EventSeverity.low,
        "vehicle moving": EventSeverity.low,
        "vehicle parked": EventSeverity.low,
        "suspicious activity": EventSeverity.high,
        "normal activity": EventSeverity.low,
        "no activity": EventSeverity.low,
    }
    
    def __init__(self):
        self.model = None
        self.processor = None
        self.classifier = None
        
        # Multi-GPU support
        self.gpu_count = torch.cuda.device_count() if torch.cuda.is_available() else 0
        self.device = "cuda" if self.gpu_count > 0 else "cpu"
        self.use_multi_gpu = self.gpu_count > 1
        
        self.model_name = "vjepa2-large"
        self.model_id = self.AVAILABLE_MODELS["vjepa2-large"]
        self.initialized = False
        self.video_buffer = VideoBuffer()
        
        # Statistics
        self._inference_count = 0
        self._total_inference_time = 0.0
        self._last_inference_time = 0.0
        
        # Log GPU info
        if self.gpu_count > 0:
            logger.info(f"🖥️ Found {self.gpu_count} GPU(s) available")
            for i in range(self.gpu_count):
                gpu_name = torch.cuda.get_device_name(i)
                gpu_mem = torch.cuda.get_device_properties(i).total_memory / 1e9
                logger.info(f"  GPU {i}: {gpu_name} ({gpu_mem:.1f} GB)")
        else:
            logger.warning("⚠️ No GPUs available, using CPU")
        
    async def initialize(self, model_name: str = "vjepa2-large", device: str = None) -> bool:
        """
        Initialize V-JEPA 2 model.
        
        Args:
            model_name: Model variant to load
            device: Device to use (cuda/cpu)
        """
        try:
            if device:
                self.device = device
                
            self.model_name = model_name
            self.model_id = self.AVAILABLE_MODELS.get(model_name, self.AVAILABLE_MODELS["vjepa2-large"])
            
            logger.info(f"🎬 Initializing V-JEPA 2 model: {self.model_name} on {self.device}")
            
            # Load model using HuggingFace transformers
            from transformers import AutoVideoProcessor, AutoModel
            
            def load_model():
                processor = AutoVideoProcessor.from_pretrained(self.model_id)
                model = AutoModel.from_pretrained(self.model_id)
                
                # Multi-GPU support with DataParallel
                if self.use_multi_gpu:
                    logger.info(f"🚀 Using DataParallel across {self.gpu_count} GPUs")
                    model = torch.nn.DataParallel(model)
                    model = model.to(self.device)
                else:
                    model = model.to(self.device)
                    
                model.eval()
                return processor, model
            
            # Run in thread to avoid blocking
            loop = asyncio.get_event_loop()
            self.processor, self.model = await loop.run_in_executor(None, load_model)
            
            # Initialize simple classifier head for surveillance activities
            await self._init_classifier()
            
            self.initialized = True
            gpu_info = f"{self.gpu_count} GPUs" if self.use_multi_gpu else self.device
            logger.info(f"✅ V-JEPA 2 initialized successfully on {gpu_info}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize V-JEPA 2: {e}")
            return False
    
    async def _init_classifier(self):
        """Initialize simple linear classifier for surveillance activities"""
        try:
            # Get feature dimension from model config
            hidden_size = self.model.config.hidden_size if hasattr(self.model.config, 'hidden_size') else 1024
            
            # Simple linear classifier
            self.classifier = torch.nn.Linear(hidden_size, len(self.SURVEILLANCE_ACTIVITIES))
            self.classifier = self.classifier.to(self.device)
            
            # Initialize with random weights (will need fine-tuning in production)
            logger.info(f"📊 Initialized activity classifier: {hidden_size} -> {len(self.SURVEILLANCE_ACTIVITIES)}")
            
        except Exception as e:
            logger.warning(f"Could not initialize classifier: {e}")
            self.classifier = None
    
    @staticmethod
    async def preload_model(model_name: str = "vjepa2-large", device: str = None) -> bool:
        """Pre-download model without fully loading into memory"""
        try:
            from huggingface_hub import snapshot_download
            
            model_id = VJEPA2Service.AVAILABLE_MODELS.get(
                model_name, 
                VJEPA2Service.AVAILABLE_MODELS["vjepa2-large"]
            )
            
            logger.info(f"📥 Pre-downloading V-JEPA 2 model: {model_id}")
            
            def download():
                snapshot_download(repo_id=model_id)
                
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, download)
            
            logger.info(f"✅ V-JEPA 2 model pre-downloaded: {model_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to pre-download V-JEPA 2: {e}")
            return False
    
    async def process_frame(self, camera_id: int, frame: np.ndarray) -> Optional[Dict[str, Any]]:
        """
        Add frame to buffer and process when ready.
        
        Args:
            camera_id: Camera identifier
            frame: BGR frame from OpenCV
            
        Returns:
            Detection result if buffer is ready, None otherwise
        """
        if not self.initialized:
            return None
            
        # Add frame to buffer
        ready = self.video_buffer.add_frame(camera_id, frame)
        
        if not ready:
            return None
            
        # Get frames for analysis
        frames = self.video_buffer.get_frames(camera_id)
        if not frames or len(frames) < 16:
            return None
            
        return await self.analyze_video(frames, camera_id)
    
    async def analyze_video(self, frames: List[np.ndarray], camera_id: int = 0) -> Dict[str, Any]:
        """
        Analyze video clip for activity detection.
        
        Args:
            frames: List of video frames (BGR numpy arrays)
            camera_id: Camera identifier
            
        Returns:
            Dictionary with detected activities and metadata
        """
        if not self.initialized or not self.model:
            return {"detections": [], "error": "Model not initialized"}
            
        start_time = datetime.now()
        
        try:
            # Convert BGR to RGB
            rgb_frames = [cv2.cvtColor(f, cv2.COLOR_BGR2RGB) for f in frames]
            
            # Process video frames
            def run_inference():
                with torch.no_grad():
                    # Prepare input
                    inputs = self.processor(rgb_frames, return_tensors="pt")
                    inputs = {k: v.to(self.device) for k, v in inputs.items()}
                    
                    # Get features
                    outputs = self.model(**inputs)
                    
                    # Pool features (use CLS token or mean pooling)
                    if hasattr(outputs, 'last_hidden_state'):
                        features = outputs.last_hidden_state.mean(dim=1)
                    elif hasattr(outputs, 'pooler_output'):
                        features = outputs.pooler_output
                    else:
                        features = outputs[0].mean(dim=1)
                    
                    return features
            
            loop = asyncio.get_event_loop()
            features = await loop.run_in_executor(None, run_inference)
            
            # Classify activity
            activity, confidence = await self._classify_activity(features)
            
            # Calculate inference time
            inference_time = (datetime.now() - start_time).total_seconds() * 1000
            self._update_stats(inference_time)
            
            # Build result
            result = {
                "detections": [],
                "timestamp": datetime.now().isoformat(),
                "inference_time_ms": inference_time,
                "frame_count": len(frames),
                "camera_id": camera_id,
            }
            
            if activity and activity != "no activity":
                detection = {
                    "class": activity,
                    "confidence": float(confidence),
                    "event_type": self.ACTIVITY_EVENT_MAPPING.get(activity),
                    "severity": self.ACTIVITY_SEVERITY_MAPPING.get(activity, EventSeverity.low),
                    "description": f"Detected: {activity}",
                    # V-JEPA 2 doesn't provide bounding boxes - it's activity recognition
                    "bbox": None,
                    "bbox_normalized": None,
                }
                result["detections"].append(detection)
                
            return result
            
        except Exception as e:
            logger.error(f"V-JEPA 2 inference error: {e}")
            return {"detections": [], "error": str(e)}
    
    async def _classify_activity(self, features: torch.Tensor) -> Tuple[str, float]:
        """Classify video features into surveillance activity"""
        if self.classifier is None:
            # Fallback: return generic activity
            return "normal activity", 0.5
            
        try:
            with torch.no_grad():
                logits = self.classifier(features)
                probs = torch.softmax(logits, dim=-1)
                confidence, idx = probs.max(dim=-1)
                
                activity = self.SURVEILLANCE_ACTIVITIES[idx.item()]
                return activity, confidence.item()
                
        except Exception as e:
            logger.warning(f"Classification error: {e}")
            return "normal activity", 0.5
    
    def _update_stats(self, inference_time: float):
        """Update inference statistics"""
        self._inference_count += 1
        self._total_inference_time += inference_time
        self._last_inference_time = inference_time
    
    def get_stats(self) -> Dict[str, Any]:
        """Get inference statistics"""
        avg_time = (
            self._total_inference_time / self._inference_count 
            if self._inference_count > 0 else 0
        )
        return {
            "model": self.model_name,
            "model_id": self.model_id,
            "device": self.device,
            "gpu_count": self.gpu_count,
            "multi_gpu": self.use_multi_gpu,
            "initialized": self.initialized,
            "inference_count": self._inference_count,
            "average_inference_time_ms": round(avg_time, 2),
            "last_inference_time_ms": round(self._last_inference_time, 2),
            "buffer_cameras": list(self.video_buffer.buffers.keys()),
        }
    
    def get_event_type(self, activity: str) -> Optional[EventType]:
        """Get event type for detected activity"""
        return self.ACTIVITY_EVENT_MAPPING.get(activity)
    
    def get_severity(self, activity: str) -> EventSeverity:
        """Get severity for detected activity"""
        return self.ACTIVITY_SEVERITY_MAPPING.get(activity, EventSeverity.low)
    
    def clear_buffer(self, camera_id: int = None):
        """Clear video buffer for camera or all cameras"""
        if camera_id:
            self.video_buffer.clear(camera_id)
        else:
            self.video_buffer.buffers.clear()
            self.video_buffer.frame_counts.clear()
    
    async def shutdown(self):
        """Cleanup resources"""
        logger.info("🛑 Shutting down V-JEPA 2 service")
        self.clear_buffer()
        if self.model:
            del self.model
            self.model = None
        if self.processor:
            del self.processor
            self.processor = None
        if self.classifier:
            del self.classifier
            self.classifier = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        self.initialized = False


# Global service instance
_vjepa2_service: Optional[VJEPA2Service] = None


async def get_vjepa2_service() -> VJEPA2Service:
    """Get or create the global V-JEPA 2 service instance"""
    global _vjepa2_service
    if _vjepa2_service is None:
        _vjepa2_service = VJEPA2Service()
    return _vjepa2_service


def get_vjepa2_service_sync() -> VJEPA2Service:
    """Synchronous getter for V-JEPA 2 service"""
    global _vjepa2_service
    if _vjepa2_service is None:
        _vjepa2_service = VJEPA2Service()
    return _vjepa2_service
