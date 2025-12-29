"""
Chowkidaar NVR - Image Embedding Service
CLIP-based image embedding for visual similarity search and cross-camera matching.
"""
import asyncio
from typing import Optional, List, Tuple, Dict, Any
from datetime import datetime
import numpy as np
from loguru import logger

# Lazy load CLIP to avoid startup delay
_clip_model = None
_clip_processor = None
CLIP_AVAILABLE = False


def get_clip_model():
    """Lazy load the CLIP model and processor."""
    global _clip_model, _clip_processor, CLIP_AVAILABLE
    
    if _clip_model is not None:
        return _clip_model, _clip_processor
    
    try:
        from transformers import CLIPProcessor, CLIPModel
        import torch
        
        logger.info("🔄 Loading CLIP model (openai/clip-vit-base-patch32)...")
        
        model_name = "openai/clip-vit-base-patch32"
        _clip_processor = CLIPProcessor.from_pretrained(model_name)
        _clip_model = CLIPModel.from_pretrained(model_name)
        
        # Move to GPU if available
        if torch.cuda.is_available():
            _clip_model = _clip_model.cuda()
            logger.info("✅ CLIP model loaded on GPU")
        else:
            logger.info("✅ CLIP model loaded on CPU")
        
        _clip_model.eval()
        CLIP_AVAILABLE = True
        
        return _clip_model, _clip_processor
        
    except ImportError as e:
        logger.warning(f"❌ CLIP not available: {e}. Install: pip install transformers torch")
        CLIP_AVAILABLE = False
        return None, None
    except Exception as e:
        logger.error(f"❌ Failed to load CLIP model: {e}")
        CLIP_AVAILABLE = False
        return None, None


class ImageEmbeddingService:
    """
    CLIP-based image embedding for visual similarity search.
    
    Features:
    - Generate 512-dim embeddings from surveillance frames
    - Find visually similar events across cameras
    - Cross-camera person/vehicle tracking potential
    - Anomaly detection via embedding distance
    
    Use cases:
    - "Find events that look like this frame"
    - "Has this person appeared at other cameras?"
    - "What visual anomalies occurred today?"
    """
    
    EMBEDDING_DIM = 512  # CLIP ViT-B/32 output dimension
    
    def __init__(self):
        self._model = None
        self._processor = None
        self._lock = asyncio.Lock()
        
    @property
    def is_available(self) -> bool:
        """Check if image embedding service is available."""
        model, _ = get_clip_model()
        return model is not None
    
    async def encode_image(self, image: np.ndarray) -> Optional[np.ndarray]:
        """
        Generate embedding from a single frame.
        
        Args:
            image: BGR numpy array from OpenCV (or RGB)
        
        Returns:
            512-dim numpy array, or None if failed
        """
        if not self.is_available:
            return None
        
        try:
            import torch
            from PIL import Image as PILImage
            
            model, processor = get_clip_model()
            
            # Convert BGR to RGB if needed
            if len(image.shape) == 3 and image.shape[2] == 3:
                # Assume BGR from OpenCV
                rgb_image = image[:, :, ::-1]
            else:
                rgb_image = image
            
            # Convert to PIL Image
            pil_image = PILImage.fromarray(rgb_image)
            
            # Process image
            inputs = processor(images=pil_image, return_tensors="pt")
            
            # Move to GPU if model is on GPU
            if next(model.parameters()).is_cuda:
                inputs = {k: v.cuda() for k, v in inputs.items()}
            
            # Get embedding
            with torch.no_grad():
                image_features = model.get_image_features(**inputs)
            
            # Normalize embedding
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)
            
            return image_features.cpu().numpy().flatten().astype(np.float32)
            
        except Exception as e:
            logger.error(f"Failed to encode image: {e}")
            return None
    
    async def encode_batch(
        self, 
        images: List[np.ndarray],
        batch_size: int = 16
    ) -> Optional[np.ndarray]:
        """
        Generate embeddings for multiple frames efficiently.
        
        Args:
            images: List of BGR numpy arrays
            batch_size: Batch size for GPU processing
        
        Returns:
            Array of shape (N, 512), or None if failed
        """
        if not self.is_available or not images:
            return None
        
        try:
            import torch
            from PIL import Image as PILImage
            
            model, processor = get_clip_model()
            
            # Convert all images to PIL
            pil_images = []
            for img in images:
                if len(img.shape) == 3 and img.shape[2] == 3:
                    rgb = img[:, :, ::-1]
                else:
                    rgb = img
                pil_images.append(PILImage.fromarray(rgb))
            
            all_embeddings = []
            
            # Process in batches
            for i in range(0, len(pil_images), batch_size):
                batch = pil_images[i:i + batch_size]
                
                inputs = processor(images=batch, return_tensors="pt", padding=True)
                
                if next(model.parameters()).is_cuda:
                    inputs = {k: v.cuda() for k, v in inputs.items()}
                
                with torch.no_grad():
                    features = model.get_image_features(**inputs)
                
                # Normalize
                features = features / features.norm(dim=-1, keepdim=True)
                all_embeddings.append(features.cpu().numpy())
            
            return np.vstack(all_embeddings).astype(np.float32)
            
        except Exception as e:
            logger.error(f"Failed to encode batch: {e}")
            return None
    
    async def encode_text(self, text: str) -> Optional[np.ndarray]:
        """
        Generate embedding from text description.
        Useful for text-to-image search (e.g., "person with red jacket").
        
        Args:
            text: Text description to encode
        
        Returns:
            512-dim numpy array, or None if failed
        """
        if not self.is_available:
            return None
        
        try:
            import torch
            
            model, processor = get_clip_model()
            
            inputs = processor(text=[text], return_tensors="pt", padding=True)
            
            if next(model.parameters()).is_cuda:
                inputs = {k: v.cuda() for k, v in inputs.items()}
            
            with torch.no_grad():
                text_features = model.get_text_features(**inputs)
            
            # Normalize
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)
            
            return text_features.cpu().numpy().flatten().astype(np.float32)
            
        except Exception as e:
            logger.error(f"Failed to encode text: {e}")
            return None
    
    def cosine_similarity(
        self, 
        embedding1: np.ndarray, 
        embedding2: np.ndarray
    ) -> float:
        """Compute cosine similarity between two embeddings."""
        return float(np.dot(embedding1, embedding2))
    
    async def find_similar_in_batch(
        self,
        query_embedding: np.ndarray,
        candidate_embeddings: np.ndarray,
        top_k: int = 5
    ) -> List[Tuple[int, float]]:
        """
        Find most similar embeddings in a batch.
        
        Args:
            query_embedding: Query vector (512,)
            candidate_embeddings: Matrix of candidates (N, 512)
            top_k: Number of results to return
        
        Returns:
            List of (index, similarity) tuples, sorted by similarity descending
        """
        if len(candidate_embeddings) == 0:
            return []
        
        # Compute cosine similarities
        similarities = np.dot(candidate_embeddings, query_embedding)
        
        # Get top-k indices
        top_indices = np.argsort(similarities)[::-1][:top_k]
        
        return [(int(idx), float(similarities[idx])) for idx in top_indices]


# Singleton instance
_image_embedding_service: Optional[ImageEmbeddingService] = None


def get_image_embedding_service() -> ImageEmbeddingService:
    """Get the singleton image embedding service instance."""
    global _image_embedding_service
    if _image_embedding_service is None:
        _image_embedding_service = ImageEmbeddingService()
    return _image_embedding_service
