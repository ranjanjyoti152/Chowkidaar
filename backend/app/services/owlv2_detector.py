"""
Chowkidaar NVR - OWLv2 Open-Vocabulary Object Detection Service
Google's OWL-ViT v2 for detecting objects using text queries
"""
import asyncio
import os
import sys
from typing import List, Dict, Any, Optional, Callable
import numpy as np
from datetime import datetime
from loguru import logger
import torch
from PIL import Image
from pathlib import Path

# Will be imported on first use to avoid startup delay
_owlv2_processor = None
_owlv2_model = None
_download_progress_callback: Optional[Callable[[str, int, int], None]] = None


def set_download_progress_callback(callback: Callable[[str, int, int], None]):
    """Set callback for download progress updates"""
    global _download_progress_callback
    _download_progress_callback = callback


class DownloadProgressBar:
    """Progress bar for model downloads"""
    
    def __init__(self, model_name: str):
        self.model_name = model_name
        self.current = 0
        self.total = 0
        self.last_percent = -1
        
    def __call__(self, current: int, total: int):
        self.current = current
        self.total = total
        if total > 0:
            percent = int(current * 100 / total)
            if percent != self.last_percent and percent % 5 == 0:
                self.last_percent = percent
                mb_current = current / (1024 * 1024)
                mb_total = total / (1024 * 1024)
                logger.info(f"📥 Downloading {self.model_name}: {percent}% ({mb_current:.1f}/{mb_total:.1f} MB)")
                if _download_progress_callback:
                    _download_progress_callback(self.model_name, current, total)


class OWLv2Detector:
    """OWLv2 Open-Vocabulary Object Detection Service"""
    
    # Available OWLv2 models
    AVAILABLE_MODELS = {
        "owlv2-base": "google/owlv2-base-patch16-ensemble",
        "owlv2-large": "google/owlv2-large-patch14-ensemble",
    }
    
    def __init__(self):
        self.model = None
        self.processor = None
        self.model_name = "owlv2-base"
        self.model_id = self.AVAILABLE_MODELS["owlv2-base"]
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.confidence_threshold = 0.1  # OWLv2 uses lower thresholds
        self._initialized = False
        self._current_model_name = None
        
        # Default text queries for detection
        self.default_queries = [
            "a person", "a car", "a dog", "a cat", "fire", "smoke",
            "a lighter", "a knife", "a gun", "a phone", "a laptop"
        ]
        self.custom_queries: List[str] = []
        
        self.inference_stats = {
            "count": 0,
            "total_time": 0.0,
            "last_time": 0.0
        }
    
    async def initialize(self, model_name: str = "owlv2-base", device: str = None, show_progress: bool = True) -> bool:
        """Initialize the OWLv2 model with download progress"""
        global _owlv2_processor, _owlv2_model
        
        if device:
            self.device = device
        
        # Skip if same model already loaded
        if self._initialized and self._current_model_name == model_name:
            logger.debug(f"OWLv2 model {model_name} already loaded")
            return True
        
        try:
            logger.info(f"🦉 Loading OWLv2 model: {model_name} on {self.device}")
            
            # Import transformers here to avoid startup delay
            from transformers import Owlv2Processor, Owlv2ForObjectDetection
            from huggingface_hub import snapshot_download
            import huggingface_hub
            
            self.model_name = model_name
            self.model_id = self.AVAILABLE_MODELS.get(model_name, self.AVAILABLE_MODELS["owlv2-base"])
            
            # Check if model is already cached
            cache_dir = Path.home() / ".cache" / "huggingface" / "hub"
            model_cache_name = f"models--{self.model_id.replace('/', '--')}"
            model_cached = (cache_dir / model_cache_name).exists()
            
            if not model_cached and show_progress:
                logger.info(f"📥 OWLv2 model not cached. Downloading {self.model_id}...")
                logger.info(f"📥 This is a one-time download (~600MB for base, ~1.2GB for large)")
                
                # Download with progress using huggingface_hub
                def download_with_progress():
                    from tqdm import tqdm
                    from huggingface_hub import HfApi, hf_hub_download, list_repo_files
                    import requests
                    
                    try:
                        # Get list of files to download
                        api = HfApi()
                        files = list_repo_files(self.model_id)
                        
                        total_files = len(files)
                        logger.info(f"📦 Downloading {total_files} files for {model_name}...")
                        
                        for i, filename in enumerate(files, 1):
                            try:
                                logger.info(f"📥 [{i}/{total_files}] Downloading: {filename}")
                                hf_hub_download(
                                    repo_id=self.model_id,
                                    filename=filename,
                                    local_dir_use_symlinks=False
                                )
                            except Exception as e:
                                logger.debug(f"File {filename}: {e}")
                        
                        logger.info(f"✅ Download complete for {model_name}")
                    except Exception as e:
                        logger.warning(f"Progress download failed, using standard download: {e}")
                
                # Run download in thread pool
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, download_with_progress)
            
            # Load in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            
            def load_model():
                logger.info(f"🔄 Loading OWLv2 model into memory...")
                processor = Owlv2Processor.from_pretrained(self.model_id)
                model = Owlv2ForObjectDetection.from_pretrained(self.model_id)
                return processor, model
            
            self.processor, self.model = await loop.run_in_executor(None, load_model)
            
            # Move to device
            if self.device == "cuda" and torch.cuda.is_available():
                self.model = self.model.to("cuda")
                logger.info(f"✅ OWLv2 model loaded on GPU: {torch.cuda.get_device_name(0)}")
            else:
                self.device = "cpu"
                self.model = self.model.to("cpu")
                logger.info("✅ OWLv2 model loaded on CPU")
            
            self.model.eval()
            self._initialized = True
            self._current_model_name = model_name
            
            # Cache globally
            _owlv2_processor = self.processor
            _owlv2_model = self.model
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to load OWLv2 model: {e}")
            return False
    
    @staticmethod
    async def preload_model(model_name: str = "owlv2-base", device: str = None) -> bool:
        """Pre-download OWLv2 model at startup without fully loading into memory"""
        try:
            from transformers import Owlv2Processor, Owlv2ForObjectDetection
            from huggingface_hub import snapshot_download, HfApi, list_repo_files
            
            model_id = OWLv2Detector.AVAILABLE_MODELS.get(model_name, OWLv2Detector.AVAILABLE_MODELS["owlv2-base"])
            
            # Check if model is already cached
            cache_dir = Path.home() / ".cache" / "huggingface" / "hub"
            model_cache_name = f"models--{model_id.replace('/', '--')}"
            
            if (cache_dir / model_cache_name).exists():
                logger.info(f"✅ OWLv2 model '{model_name}' already cached")
                return True
            
            logger.info(f"📥 Pre-downloading OWLv2 model: {model_name}")
            logger.info(f"📥 Model ID: {model_id}")
            logger.info(f"📥 This may take a few minutes on first run...")
            
            loop = asyncio.get_event_loop()
            
            def download_model():
                try:
                    # Get file list for progress
                    api = HfApi()
                    files = list_repo_files(model_id)
                    total_files = len(files)
                    
                    logger.info(f"📦 Total files to download: {total_files}")
                    
                    # Use snapshot_download for efficient caching
                    snapshot_download(
                        repo_id=model_id,
                        local_dir_use_symlinks=False
                    )
                    
                    logger.info(f"✅ OWLv2 model '{model_name}' downloaded successfully!")
                    return True
                except Exception as e:
                    logger.error(f"❌ Failed to download OWLv2 model: {e}")
                    return False
            
            result = await loop.run_in_executor(None, download_model)
            return result
            
        except ImportError as e:
            logger.warning(f"⚠️ OWLv2 dependencies not installed: {e}")
            logger.warning("⚠️ Install with: pip install transformers accelerate")
            return False
        except Exception as e:
            logger.error(f"❌ Error pre-downloading OWLv2: {e}")
            return False
    
    def set_custom_queries(self, queries: List[str]):
        """Set custom text queries for detection"""
        if queries:
            self.custom_queries = queries
            logger.info(f"🦉 OWLv2 custom queries set: {queries}")
    
    def get_active_queries(self) -> List[str]:
        """Get the active text queries (custom if set, otherwise default)"""
        return self.custom_queries if self.custom_queries else self.default_queries
    
    async def detect(
        self,
        frame: np.ndarray,
        queries: Optional[List[str]] = None,
        confidence_threshold: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Perform open-vocabulary object detection on a frame
        
        Args:
            frame: numpy array (BGR format from OpenCV)
            queries: List of text queries to detect (e.g., ["a person", "fire", "lighter"])
            confidence_threshold: Minimum confidence for detections
        
        Returns:
            Dictionary containing detected objects and metadata
        """
        if not self._initialized or self.model is None:
            logger.warning("OWLv2 model not initialized")
            return {"objects": [], "metadata": {"error": "Model not initialized"}}
        
        # Use provided queries or active queries
        text_queries = queries or self.get_active_queries()
        conf_threshold = confidence_threshold or self.confidence_threshold
        
        start_time = datetime.utcnow()
        
        try:
            # Convert BGR to RGB
            if len(frame.shape) == 3 and frame.shape[2] == 3:
                rgb_frame = frame[:, :, ::-1]  # BGR to RGB
            else:
                rgb_frame = frame
            
            # Convert to PIL Image
            pil_image = Image.fromarray(rgb_frame)
            
            # Run inference in thread pool
            loop = asyncio.get_event_loop()
            
            def run_inference():
                # Process image and text
                inputs = self.processor(
                    text=[text_queries],  # Batch of queries
                    images=pil_image,
                    return_tensors="pt"
                )
                
                # Move inputs to device
                inputs = {k: v.to(self.device) for k, v in inputs.items()}
                
                with torch.no_grad():
                    outputs = self.model(**inputs)
                
                # Post-process
                target_sizes = torch.tensor([pil_image.size[::-1]]).to(self.device)
                results = self.processor.post_process_object_detection(
                    outputs,
                    threshold=conf_threshold,
                    target_sizes=target_sizes
                )[0]
                
                return results
            
            results = await loop.run_in_executor(None, run_inference)
            
            # Calculate inference time
            inference_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            self._update_stats(inference_time)
            
            # Process results
            detected_objects = []
            boxes = results["boxes"].cpu().numpy()
            scores = results["scores"].cpu().numpy()
            labels = results["labels"].cpu().numpy()
            
            for box, score, label_idx in zip(boxes, scores, labels):
                if score >= conf_threshold:
                    x1, y1, x2, y2 = box.tolist()
                    class_name = text_queries[label_idx] if label_idx < len(text_queries) else "unknown"
                    
                    # Clean up class name (remove "a " prefix)
                    clean_name = class_name.replace("a ", "").replace("an ", "").strip()
                    
                    detected_objects.append({
                        "class_id": int(label_idx),
                        "class_name": clean_name,
                        "confidence": float(score),
                        "bbox": [x1, y1, x2, y2],
                        "bbox_normalized": self._normalize_bbox([x1, y1, x2, y2], frame.shape),
                        "query": class_name  # Original query
                    })
            
            return {
                "objects": detected_objects,
                "metadata": {
                    "inference_time_ms": inference_time,
                    "frame_shape": frame.shape,
                    "model": self.model_name,
                    "queries": text_queries,
                    "device": self.device,
                    "confidence_threshold": conf_threshold
                }
            }
            
        except Exception as e:
            logger.error(f"OWLv2 detection error: {e}")
            return {
                "objects": [],
                "metadata": {"error": str(e)}
            }
    
    def _normalize_bbox(self, bbox: List[float], frame_shape: tuple) -> List[float]:
        """Normalize bounding box to [0, 1] range"""
        h, w = frame_shape[:2]
        return [
            bbox[0] / w,  # x1
            bbox[1] / h,  # y1
            bbox[2] / w,  # x2
            bbox[3] / h   # y2
        ]
    
    def _update_stats(self, inference_time: float):
        """Update inference statistics"""
        self.inference_stats["count"] += 1
        self.inference_stats["total_time"] += inference_time
        self.inference_stats["last_time"] = inference_time
    
    def get_stats(self) -> Dict[str, Any]:
        """Get inference statistics"""
        avg_time = 0
        if self.inference_stats["count"] > 0:
            avg_time = self.inference_stats["total_time"] / self.inference_stats["count"]
        
        return {
            "model": self.model_name,
            "device": self.device,
            "inference_count": self.inference_stats["count"],
            "avg_inference_time_ms": avg_time,
            "last_inference_time_ms": self.inference_stats["last_time"],
            "active_queries": self.get_active_queries(),
            "initialized": self._initialized
        }
    
    def draw_detections(
        self,
        frame: np.ndarray,
        detections: List[Dict[str, Any]],
        color: tuple = (0, 255, 0),
        thickness: int = 2
    ) -> np.ndarray:
        """Draw detection boxes on frame"""
        import cv2
        
        annotated = frame.copy()
        
        for det in detections:
            bbox = det["bbox"]
            x1, y1, x2, y2 = map(int, bbox)
            
            # Draw box
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, thickness)
            
            # Draw label
            label = f"{det['class_name']}: {det['confidence']:.2f}"
            label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
            
            # Background for label
            cv2.rectangle(
                annotated,
                (x1, y1 - label_size[1] - 10),
                (x1 + label_size[0], y1),
                color,
                -1
            )
            
            # Label text
            cv2.putText(
                annotated,
                label,
                (x1, y1 - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 0, 0),
                2
            )
        
        return annotated


# Global instance
_owlv2_detector: Optional[OWLv2Detector] = None


async def get_owlv2_detector() -> OWLv2Detector:
    """Get or create the global OWLv2 detector instance"""
    global _owlv2_detector
    if _owlv2_detector is None:
        _owlv2_detector = OWLv2Detector()
    return _owlv2_detector
