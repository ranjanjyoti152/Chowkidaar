"""
Chowkidaar NVR - VLM Cache Service
Perceptual hash-based caching for VLM responses to reduce inference costs.

Uses perceptual hashing (pHash) to identify similar frames and reuse
previously generated VLM summaries.
"""
import asyncio
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from loguru import logger
import numpy as np
from collections import OrderedDict

try:
    import imagehash
    from PIL import Image
    IMAGEHASH_AVAILABLE = True
except ImportError:
    IMAGEHASH_AVAILABLE = False
    logger.warning("imagehash not installed. VLM caching disabled. Install: pip install imagehash")


class VLMCacheEntry:
    """Single cache entry with metadata."""
    
    def __init__(
        self,
        phash: str,
        summary: str,
        severity: str,
        event_type: str,
        created_at: datetime,
        camera_id: int,
        detection_classes: Tuple[str, ...]
    ):
        self.phash = phash
        self.summary = summary
        self.severity = severity
        self.event_type = event_type
        self.created_at = created_at
        self.camera_id = camera_id
        self.detection_classes = detection_classes
        self.hit_count = 0
    
    def is_expired(self, ttl_seconds: int = 300) -> bool:
        """Check if cache entry has expired."""
        return (datetime.now() - self.created_at).total_seconds() > ttl_seconds


class VLMCacheService:
    """
    Perceptual hash-based VLM response caching.
    
    Features:
    - Compute pHash of incoming frames
    - If similar frame (hamming distance < threshold) seen recently, reuse summary
    - TTL-based cache expiration (default 5 minutes for same scene)
    - Camera-specific caching (same camera = likely similar context)
    - LRU eviction when cache is full
    
    Benefits:
    - Reduces redundant VLM calls for static scenes
    - Significantly lowers inference costs
    - Near-instant response for cached scenes
    """
    
    def __init__(
        self,
        max_entries: int = 1000,
        ttl_seconds: int = 300,
        hamming_threshold: int = 10
    ):
        self.max_entries = max_entries
        self.ttl_seconds = ttl_seconds
        self.hamming_threshold = hamming_threshold
        
        # LRU cache: phash -> CacheEntry
        self._cache: OrderedDict[str, VLMCacheEntry] = OrderedDict()
        self._lock = asyncio.Lock()
        
        # Statistics
        self.hits = 0
        self.misses = 0
        self.total_requests = 0
    
    def is_available(self) -> bool:
        """Check if caching is available (imagehash installed)."""
        return IMAGEHASH_AVAILABLE
    
    def compute_phash(self, frame: np.ndarray, hash_size: int = 16) -> Optional[str]:
        """
        Compute perceptual hash of a frame.
        
        Args:
            frame: BGR numpy array from OpenCV
            hash_size: Hash size (larger = more precise, 8-16 recommended)
        
        Returns:
            Hex string of perceptual hash, or None if failed
        """
        if not IMAGEHASH_AVAILABLE:
            return None
        
        try:
            # Convert BGR to RGB and create PIL Image
            if len(frame.shape) == 3 and frame.shape[2] == 3:
                rgb_frame = frame[:, :, ::-1]  # BGR to RGB
            else:
                rgb_frame = frame
            
            pil_image = Image.fromarray(rgb_frame)
            
            # Compute perceptual hash
            phash = imagehash.phash(pil_image, hash_size=hash_size)
            return str(phash)
            
        except Exception as e:
            logger.warning(f"Failed to compute pHash: {e}")
            return None
    
    def _hamming_distance(self, hash1: str, hash2: str) -> int:
        """Compute Hamming distance between two hex hash strings."""
        try:
            h1 = imagehash.hex_to_hash(hash1)
            h2 = imagehash.hex_to_hash(hash2)
            return h1 - h2
        except Exception:
            return 999  # Return high distance on error
    
    async def get(
        self,
        frame: np.ndarray,
        camera_id: int,
        detection_classes: Tuple[str, ...]
    ) -> Optional[VLMCacheEntry]:
        """
        Try to find a cached VLM response for a similar frame.
        
        Args:
            frame: Current frame to check
            camera_id: Camera ID (for camera-specific caching)
            detection_classes: Tuple of detected class names
        
        Returns:
            CacheEntry if found, None otherwise
        """
        if not IMAGEHASH_AVAILABLE:
            return None
        
        self.total_requests += 1
        
        frame_hash = self.compute_phash(frame)
        if not frame_hash:
            self.misses += 1
            return None
        
        async with self._lock:
            # First, try exact match (same hash)
            if frame_hash in self._cache:
                entry = self._cache[frame_hash]
                if not entry.is_expired(self.ttl_seconds):
                    # Check if detection classes match
                    if entry.camera_id == camera_id and entry.detection_classes == detection_classes:
                        entry.hit_count += 1
                        self.hits += 1
                        # Move to end (LRU)
                        self._cache.move_to_end(frame_hash)
                        logger.debug(f"Cache HIT (exact): {frame_hash[:16]}...")
                        return entry
            
            # Try fuzzy match (similar hash within threshold)
            for cached_hash, entry in list(self._cache.items()):
                if entry.is_expired(self.ttl_seconds):
                    del self._cache[cached_hash]
                    continue
                
                # Skip if different camera or detection classes
                if entry.camera_id != camera_id:
                    continue
                if entry.detection_classes != detection_classes:
                    continue
                
                distance = self._hamming_distance(frame_hash, cached_hash)
                if distance <= self.hamming_threshold:
                    entry.hit_count += 1
                    self.hits += 1
                    self._cache.move_to_end(cached_hash)
                    logger.debug(f"Cache HIT (fuzzy, dist={distance}): {cached_hash[:16]}...")
                    return entry
        
        self.misses += 1
        return None
    
    async def put(
        self,
        frame: np.ndarray,
        camera_id: int,
        detection_classes: Tuple[str, ...],
        summary: str,
        severity: str,
        event_type: str
    ) -> bool:
        """
        Cache a VLM response for a frame.
        
        Returns:
            True if cached successfully, False otherwise
        """
        if not IMAGEHASH_AVAILABLE:
            return False
        
        frame_hash = self.compute_phash(frame)
        if not frame_hash:
            return False
        
        async with self._lock:
            # Evict oldest if at capacity
            while len(self._cache) >= self.max_entries:
                self._cache.popitem(last=False)
            
            # Add new entry
            entry = VLMCacheEntry(
                phash=frame_hash,
                summary=summary,
                severity=severity,
                event_type=event_type,
                created_at=datetime.now(),
                camera_id=camera_id,
                detection_classes=detection_classes
            )
            self._cache[frame_hash] = entry
            logger.debug(f"Cache PUT: {frame_hash[:16]}... (size={len(self._cache)})")
            return True
    
    async def invalidate_camera(self, camera_id: int) -> int:
        """Invalidate all cache entries for a specific camera."""
        async with self._lock:
            to_remove = [
                h for h, e in self._cache.items() 
                if e.camera_id == camera_id
            ]
            for h in to_remove:
                del self._cache[h]
            return len(to_remove)
    
    async def clear(self):
        """Clear all cache entries."""
        async with self._lock:
            self._cache.clear()
            self.hits = 0
            self.misses = 0
            self.total_requests = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        hit_rate = (self.hits / self.total_requests * 100) if self.total_requests > 0 else 0
        return {
            "total_requests": self.total_requests,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate_percent": round(hit_rate, 2),
            "cache_size": len(self._cache),
            "max_entries": self.max_entries,
            "ttl_seconds": self.ttl_seconds,
            "imagehash_available": IMAGEHASH_AVAILABLE
        }


# Singleton instance
_vlm_cache: Optional[VLMCacheService] = None


def get_vlm_cache() -> VLMCacheService:
    """Get the singleton VLM cache service instance."""
    global _vlm_cache
    if _vlm_cache is None:
        _vlm_cache = VLMCacheService()
    return _vlm_cache
