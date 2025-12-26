"""
Chowkidaar NVR - Event Embedding Service
Vector embeddings for semantic search of surveillance events
"""
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import logging
import asyncio
from functools import lru_cache

logger = logging.getLogger(__name__)

# Lazy load to avoid startup delay
_embedding_model = None
_faiss_index = None


def get_embedding_model():
    """Lazy load the sentence transformer model"""
    global _embedding_model
    if _embedding_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            logger.info("🔄 Loading embedding model (all-MiniLM-L6-v2)...")
            _embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
            logger.info("✅ Embedding model loaded successfully")
        except ImportError:
            logger.warning("❌ sentence-transformers not installed. Run: pip install sentence-transformers")
            return None
        except Exception as e:
            logger.error(f"❌ Failed to load embedding model: {e}")
            return None
    return _embedding_model


class EventEmbeddingService:
    """
    Service for generating and searching event embeddings.
    Uses sentence-transformers for encoding and FAISS for similarity search.
    """
    
    def __init__(self):
        self.embedding_dim = 384  # all-MiniLM-L6-v2 dimension
        self.event_embeddings: Dict[int, np.ndarray] = {}  # event_id -> embedding
        self.event_metadata: Dict[int, Dict[str, Any]] = {}  # event_id -> metadata
        self._index = None
        self._event_ids: List[int] = []  # Ordered list of event IDs in index
        
    @property
    def model(self):
        return get_embedding_model()
    
    def is_available(self) -> bool:
        """Check if embedding service is available"""
        return self.model is not None
    
    def encode(self, text: str) -> Optional[np.ndarray]:
        """Encode text to embedding vector"""
        if not self.is_available():
            return None
        try:
            embedding = self.model.encode(text, convert_to_numpy=True)
            return embedding.astype(np.float32)
        except Exception as e:
            logger.error(f"Encoding error: {e}")
            return None
    
    def encode_batch(self, texts: List[str]) -> Optional[np.ndarray]:
        """Encode multiple texts to embedding vectors"""
        if not self.is_available() or not texts:
            return None
        try:
            embeddings = self.model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
            return embeddings.astype(np.float32)
        except Exception as e:
            logger.error(f"Batch encoding error: {e}")
            return None
    
    def create_event_text(self, event_data: Dict[str, Any]) -> str:
        """
        Create searchable text from event data.
        Combines summary, detected objects, camera name, and event type.
        """
        parts = []
        
        # Camera name with context
        if event_data.get('camera_name'):
            parts.append(f"Camera: {event_data['camera_name']}")
        
        # Event type in human readable form
        event_type = event_data.get('event_type', '').replace('_', ' ')
        if event_type:
            parts.append(f"Event: {event_type}")
        
        # Severity
        if event_data.get('severity'):
            parts.append(f"Severity: {event_data['severity']}")
        
        # Detected objects
        detected_objects = event_data.get('detected_objects', [])
        if isinstance(detected_objects, dict):
            detected_objects = detected_objects.get('objects', [])
        if detected_objects:
            if isinstance(detected_objects[0], dict):
                obj_names = [obj.get('class_name', '') for obj in detected_objects]
            else:
                obj_names = detected_objects
            parts.append(f"Objects: {', '.join(obj_names)}")
        
        # Summary (most important)
        if event_data.get('summary'):
            parts.append(event_data['summary'])
        
        # Timestamp context
        timestamp = event_data.get('timestamp')
        if timestamp:
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            if isinstance(timestamp, datetime):
                hour = timestamp.hour
                if 0 <= hour < 6:
                    time_context = "late night"
                elif 6 <= hour < 12:
                    time_context = "morning"
                elif 12 <= hour < 17:
                    time_context = "afternoon"
                elif 17 <= hour < 21:
                    time_context = "evening"
                else:
                    time_context = "night"
                parts.append(f"Time: {time_context}")
        
        return " | ".join(parts)
    
    def add_event(self, event_id: int, event_data: Dict[str, Any]) -> bool:
        """Add an event to the embedding index"""
        text = self.create_event_text(event_data)
        embedding = self.encode(text)
        
        if embedding is None:
            return False
        
        self.event_embeddings[event_id] = embedding
        self.event_metadata[event_id] = {
            'camera_id': event_data.get('camera_id'),
            'camera_name': event_data.get('camera_name'),
            'event_type': event_data.get('event_type'),
            'severity': event_data.get('severity'),
            'timestamp': event_data.get('timestamp'),
            'summary': event_data.get('summary'),
            'text': text
        }
        
        # Invalidate index (will be rebuilt on next search)
        self._index = None
        
        return True
    
    def add_events_batch(self, events: List[Dict[str, Any]]) -> int:
        """Add multiple events efficiently"""
        if not events:
            return 0
        
        texts = []
        valid_events = []
        
        for event in events:
            text = self.create_event_text(event)
            texts.append(text)
            valid_events.append(event)
        
        embeddings = self.encode_batch(texts)
        if embeddings is None:
            return 0
        
        count = 0
        for i, event in enumerate(valid_events):
            event_id = event.get('id')
            if event_id is not None:
                self.event_embeddings[event_id] = embeddings[i]
                self.event_metadata[event_id] = {
                    'camera_id': event.get('camera_id'),
                    'camera_name': event.get('camera_name'),
                    'event_type': event.get('event_type'),
                    'severity': event.get('severity'),
                    'timestamp': event.get('timestamp'),
                    'summary': event.get('summary'),
                    'text': texts[i]
                }
                count += 1
        
        # Invalidate index
        self._index = None
        
        return count
    
    def _build_index(self):
        """Build FAISS index from current embeddings"""
        if not self.event_embeddings:
            self._index = None
            self._event_ids = []
            return
        
        try:
            import faiss
        except ImportError:
            logger.warning("FAISS not installed, using numpy-based search. Install: pip install faiss-cpu")
            self._index = None
            return
        
        self._event_ids = list(self.event_embeddings.keys())
        embeddings = np.array([self.event_embeddings[eid] for eid in self._event_ids])
        
        # Create index (L2 distance)
        self._index = faiss.IndexFlatL2(self.embedding_dim)
        self._index.add(embeddings)
        
        logger.info(f"📊 Built FAISS index with {len(self._event_ids)} events")
    
    def search(
        self,
        query: str,
        camera_id: Optional[int] = None,
        camera_name: Optional[str] = None,
        top_k: int = 10,
        min_score: float = 0.0
    ) -> List[Tuple[int, float, Dict[str, Any]]]:
        """
        Search for similar events using vector similarity.
        
        Args:
            query: Search query text
            camera_id: Optional filter by camera ID
            camera_name: Optional filter by camera name
            top_k: Number of results to return
            min_score: Minimum similarity score (0-1)
            
        Returns:
            List of (event_id, similarity_score, metadata) tuples
        """
        if not self.event_embeddings:
            return []
        
        query_embedding = self.encode(query)
        if query_embedding is None:
            return []
        
        # Filter events by camera if specified
        candidate_ids = list(self.event_embeddings.keys())
        if camera_id is not None:
            candidate_ids = [
                eid for eid in candidate_ids
                if self.event_metadata.get(eid, {}).get('camera_id') == camera_id
            ]
        if camera_name is not None:
            camera_name_lower = camera_name.lower()
            candidate_ids = [
                eid for eid in candidate_ids
                if camera_name_lower in (self.event_metadata.get(eid, {}).get('camera_name', '') or '').lower()
            ]
        
        if not candidate_ids:
            return []
        
        # Try FAISS search first
        try:
            import faiss
            if self._index is None or len(self._event_ids) != len(self.event_embeddings):
                self._build_index()
            
            if self._index is not None:
                # Search full index then filter
                distances, indices = self._index.search(
                    query_embedding.reshape(1, -1),
                    min(top_k * 3, len(self._event_ids))  # Get more to filter
                )
                
                results = []
                for dist, idx in zip(distances[0], indices[0]):
                    if idx < 0:
                        continue
                    event_id = self._event_ids[idx]
                    
                    # Apply camera filter
                    if camera_id is not None and self.event_metadata.get(event_id, {}).get('camera_id') != camera_id:
                        continue
                    if camera_name is not None and camera_name_lower not in (self.event_metadata.get(event_id, {}).get('camera_name', '') or '').lower():
                        continue
                    
                    # Convert L2 distance to similarity score (0-1)
                    similarity = 1 / (1 + dist)
                    
                    if similarity >= min_score:
                        results.append((
                            event_id,
                            float(similarity),
                            self.event_metadata.get(event_id, {})
                        ))
                    
                    if len(results) >= top_k:
                        break
                
                return results
        except ImportError:
            pass
        
        # Fallback to numpy-based search
        candidate_embeddings = np.array([self.event_embeddings[eid] for eid in candidate_ids])
        
        # Cosine similarity
        query_norm = query_embedding / np.linalg.norm(query_embedding)
        embeddings_norm = candidate_embeddings / np.linalg.norm(candidate_embeddings, axis=1, keepdims=True)
        similarities = np.dot(embeddings_norm, query_norm)
        
        # Get top-k
        top_indices = np.argsort(similarities)[::-1][:top_k]
        
        results = []
        for idx in top_indices:
            similarity = float(similarities[idx])
            if similarity >= min_score:
                event_id = candidate_ids[idx]
                results.append((
                    event_id,
                    similarity,
                    self.event_metadata.get(event_id, {})
                ))
        
        return results
    
    def get_camera_summary(self, camera_id: Optional[int] = None, camera_name: Optional[str] = None) -> Dict[str, Any]:
        """Get event statistics for a specific camera"""
        stats = {
            'total_events': 0,
            'event_types': {},
            'severity_counts': {},
            'recent_events': []
        }
        
        for event_id, metadata in self.event_metadata.items():
            # Filter by camera
            if camera_id is not None and metadata.get('camera_id') != camera_id:
                continue
            if camera_name is not None and camera_name.lower() not in (metadata.get('camera_name', '') or '').lower():
                continue
            
            stats['total_events'] += 1
            
            # Count event types
            event_type = metadata.get('event_type', 'unknown')
            stats['event_types'][event_type] = stats['event_types'].get(event_type, 0) + 1
            
            # Count severities
            severity = metadata.get('severity', 'unknown')
            stats['severity_counts'][severity] = stats['severity_counts'].get(severity, 0) + 1
            
            # Track recent events
            stats['recent_events'].append({
                'id': event_id,
                'summary': metadata.get('summary', '')[:100],
                'timestamp': metadata.get('timestamp')
            })
        
        # Sort recent events by timestamp
        stats['recent_events'] = sorted(
            stats['recent_events'],
            key=lambda x: x.get('timestamp') or datetime.min,
            reverse=True
        )[:5]
        
        return stats
    
    def remove_event(self, event_id: int) -> bool:
        """Remove a single event from the embedding index"""
        if event_id in self.event_embeddings:
            del self.event_embeddings[event_id]
            if event_id in self.event_metadata:
                del self.event_metadata[event_id]
            self._index = None  # Invalidate index
            logger.debug(f"🗑️ Removed embedding for event {event_id}")
            return True
        return False
    
    def remove_events(self, event_ids: List[int]) -> int:
        """Remove multiple events from the embedding index"""
        removed = 0
        for event_id in event_ids:
            if self.remove_event(event_id):
                removed += 1
        if removed > 0:
            logger.info(f"🗑️ Removed {removed} event embeddings")
        return removed
    
    def remove_camera_events(self, camera_id: int) -> int:
        """Remove all events for a specific camera from the embedding index"""
        events_to_remove = [
            event_id for event_id, metadata in self.event_metadata.items()
            if metadata.get('camera_id') == camera_id
        ]
        
        removed = 0
        for event_id in events_to_remove:
            if event_id in self.event_embeddings:
                del self.event_embeddings[event_id]
            if event_id in self.event_metadata:
                del self.event_metadata[event_id]
            removed += 1
        
        if removed > 0:
            self._index = None  # Invalidate index
            logger.info(f"🗑️ Removed {removed} embeddings for camera {camera_id}")
        
        return removed
    
    def clear(self):
        """Clear all embeddings"""
        self.event_embeddings.clear()
        self.event_metadata.clear()
        self._index = None
        self._event_ids = []


# Singleton instance
_embedding_service: Optional[EventEmbeddingService] = None


def get_embedding_service() -> EventEmbeddingService:
    """Get the singleton embedding service instance"""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EventEmbeddingService()
    return _embedding_service


async def initialize_embeddings_from_db(db_session):
    """
    Initialize embedding index from database events.
    Called on application startup.
    """
    from app.models.event import Event
    from app.models.camera import Camera
    from sqlalchemy import select
    
    service = get_embedding_service()
    
    if not service.is_available():
        logger.warning("⚠️ Embedding service not available (sentence-transformers not installed)")
        return
    
    logger.info("🔄 Building event embedding index from database...")
    
    try:
        # Get recent events with camera info
        result = await db_session.execute(
            select(Event, Camera.name.label("camera_name"))
            .join(Camera, Event.camera_id == Camera.id)
            .where(Event.summary.isnot(None))  # Only events with summaries
            .order_by(Event.timestamp.desc())
            .limit(1000)  # Limit for memory efficiency
        )
        rows = result.all()
        
        if not rows:
            logger.info("📊 No events to index")
            return
        
        events = []
        for row in rows:
            event = row[0]
            camera_name = row[1]
            events.append({
                'id': event.id,
                'camera_id': event.camera_id,
                'camera_name': camera_name,
                'event_type': event.event_type.value if event.event_type else None,
                'severity': event.severity.value if event.severity else None,
                'timestamp': event.timestamp,
                'summary': event.summary,
                'detected_objects': event.detected_objects
            })
        
        count = service.add_events_batch(events)
        logger.info(f"✅ Indexed {count} events for semantic search")
        
    except Exception as e:
        logger.error(f"❌ Error building embedding index: {e}")
