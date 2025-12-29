"""
Chowkidaar NVR - pgvector Embedding Service
PostgreSQL-based vector storage and search replacing in-memory FAISS.
"""
import asyncio
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
import numpy as np
from loguru import logger

from app.core.database import AsyncSessionLocal
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession


class PgVectorEmbeddingService:
    """
    Persistent embedding storage and search using PostgreSQL pgvector.
    
    Advantages over FAISS:
    - Persistent storage (survives restarts)
    - Scalable to millions of events
    - Integrated with existing PostgreSQL database
    - Supports hybrid queries (vector + filters)
    - HNSW indexes for fast approximate search
    
    Features:
    - Text embeddings (384 dims - all-MiniLM-L6-v2)
    - Image embeddings (512 dims - CLIP ViT-B/32)
    - Combined text + image search
    - Camera and time range filtering
    """
    
    TEXT_EMBEDDING_DIM = 384
    IMAGE_EMBEDDING_DIM = 512
    
    def __init__(self):
        self._text_encoder = None
        self._image_encoder = None
    
    @property
    def text_encoder(self):
        """Lazy load text encoder."""
        if self._text_encoder is None:
            from app.services.embedding_service import get_embedding_service
            self._text_encoder = get_embedding_service()
        return self._text_encoder
    
    @property
    def image_encoder(self):
        """Lazy load image encoder."""
        if self._image_encoder is None:
            from app.services.image_embedding_service import get_image_embedding_service
            self._image_encoder = get_image_embedding_service()
        return self._image_encoder
    
    async def store_text_embedding(
        self,
        event_id: int,
        text: str,
        db: Optional[AsyncSession] = None
    ) -> bool:
        """
        Generate and store text embedding for an event.
        
        Args:
            event_id: Event ID to update
            text: Text to encode (summary + metadata)
            db: Optional database session (creates new if not provided)
        
        Returns:
            True if successful
        """
        try:
            embedding = self.text_encoder.encode(text)
            if embedding is None:
                return False
            
            # Convert to list for PostgreSQL
            embedding_list = embedding.tolist()
            
            async with AsyncSessionLocal() as session:
                db_session = db or session
                
                # Update event with embedding
                await db_session.execute(
                    text("""
                        UPDATE events 
                        SET text_embedding = :embedding
                        WHERE id = :event_id
                    """),
                    {"embedding": str(embedding_list), "event_id": event_id}
                )
                
                if db is None:
                    await db_session.commit()
                
                return True
                
        except Exception as e:
            logger.error(f"Failed to store text embedding for event {event_id}: {e}")
            return False
    
    async def store_image_embedding(
        self,
        event_id: int,
        image: np.ndarray,
        db: Optional[AsyncSession] = None
    ) -> bool:
        """
        Generate and store image embedding for an event.
        
        Args:
            event_id: Event ID to update
            image: Frame to encode
            db: Optional database session
        
        Returns:
            True if successful
        """
        try:
            embedding = await self.image_encoder.encode_image(image)
            if embedding is None:
                return False
            
            embedding_list = embedding.tolist()
            
            async with AsyncSessionLocal() as session:
                db_session = db or session
                
                await db_session.execute(
                    text("""
                        UPDATE events 
                        SET image_embedding = :embedding
                        WHERE id = :event_id
                    """),
                    {"embedding": str(embedding_list), "event_id": event_id}
                )
                
                if db is None:
                    await db_session.commit()
                
                return True
                
        except Exception as e:
            logger.error(f"Failed to store image embedding for event {event_id}: {e}")
            return False
    
    async def search_by_text(
        self,
        query: str,
        camera_id: Optional[int] = None,
        user_id: Optional[int] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        top_k: int = 10,
        min_similarity: float = 0.3
    ) -> List[Dict[str, Any]]:
        """
        Search events by text query using vector similarity.
        
        Args:
            query: Search query text
            camera_id: Optional filter by camera
            user_id: Optional filter by user
            start_time: Optional start of time range
            end_time: Optional end of time range
            top_k: Number of results to return
            min_similarity: Minimum cosine similarity (0-1)
        
        Returns:
            List of event dicts with similarity scores
        """
        try:
            # Encode query
            query_embedding = self.text_encoder.encode(query)
            if query_embedding is None:
                return []
            
            # Build SQL query with filters
            filters = ["text_embedding IS NOT NULL"]
            params = {
                "embedding": str(query_embedding.tolist()),
                "limit": top_k,
                "min_distance": 1 - min_similarity  # cosine distance = 1 - similarity
            }
            
            if camera_id:
                filters.append("camera_id = :camera_id")
                params["camera_id"] = camera_id
            
            if user_id:
                filters.append("user_id = :user_id")
                params["user_id"] = user_id
            
            if start_time:
                filters.append("timestamp >= :start_time")
                params["start_time"] = start_time
            
            if end_time:
                filters.append("timestamp <= :end_time")
                params["end_time"] = end_time
            
            filter_clause = " AND ".join(filters)
            
            sql = f"""
                SELECT 
                    id, event_type, severity, summary, timestamp,
                    camera_id, frame_path, confidence_score,
                    1 - (text_embedding <=> :embedding::vector) as similarity
                FROM events
                WHERE {filter_clause}
                    AND (text_embedding <=> :embedding::vector) < :min_distance
                ORDER BY text_embedding <=> :embedding::vector
                LIMIT :limit
            """
            
            async with AsyncSessionLocal() as db:
                result = await db.execute(text(sql), params)
                rows = result.fetchall()
            
            return [
                {
                    "id": row.id,
                    "event_type": row.event_type,
                    "severity": row.severity,
                    "summary": row.summary,
                    "timestamp": row.timestamp.isoformat() if row.timestamp else None,
                    "camera_id": row.camera_id,
                    "frame_path": row.frame_path,
                    "confidence_score": row.confidence_score,
                    "similarity": round(row.similarity, 4)
                }
                for row in rows
            ]
            
        except Exception as e:
            logger.error(f"Text search failed: {e}")
            return []
    
    async def search_by_image(
        self,
        image: np.ndarray,
        camera_id: Optional[int] = None,
        exclude_camera_id: Optional[int] = None,
        top_k: int = 10,
        min_similarity: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        Search events by image similarity.
        Great for cross-camera matching and visual anomaly detection.
        
        Args:
            image: Query frame
            camera_id: Optional filter to specific camera
            exclude_camera_id: Optional exclude specific camera (for cross-camera search)
            top_k: Number of results
            min_similarity: Minimum cosine similarity
        
        Returns:
            List of event dicts with similarity scores
        """
        try:
            query_embedding = await self.image_encoder.encode_image(image)
            if query_embedding is None:
                return []
            
            filters = ["image_embedding IS NOT NULL"]
            params = {
                "embedding": str(query_embedding.tolist()),
                "limit": top_k,
                "min_distance": 1 - min_similarity
            }
            
            if camera_id:
                filters.append("camera_id = :camera_id")
                params["camera_id"] = camera_id
            
            if exclude_camera_id:
                filters.append("camera_id != :exclude_camera_id")
                params["exclude_camera_id"] = exclude_camera_id
            
            filter_clause = " AND ".join(filters)
            
            sql = f"""
                SELECT 
                    id, event_type, severity, summary, timestamp,
                    camera_id, frame_path,
                    1 - (image_embedding <=> :embedding::vector) as similarity
                FROM events
                WHERE {filter_clause}
                    AND (image_embedding <=> :embedding::vector) < :min_distance
                ORDER BY image_embedding <=> :embedding::vector
                LIMIT :limit
            """
            
            async with AsyncSessionLocal() as db:
                result = await db.execute(text(sql), params)
                rows = result.fetchall()
            
            return [
                {
                    "id": row.id,
                    "event_type": row.event_type,
                    "severity": row.severity,
                    "summary": row.summary,
                    "timestamp": row.timestamp.isoformat() if row.timestamp else None,
                    "camera_id": row.camera_id,
                    "frame_path": row.frame_path,
                    "similarity": round(row.similarity, 4)
                }
                for row in rows
            ]
            
        except Exception as e:
            logger.error(f"Image search failed: {e}")
            return []
    
    async def get_embedding_stats(self) -> Dict[str, Any]:
        """Get statistics about stored embeddings."""
        try:
            async with AsyncSessionLocal() as db:
                result = await db.execute(text("""
                    SELECT 
                        COUNT(*) as total_events,
                        COUNT(text_embedding) as text_embeddings,
                        COUNT(image_embedding) as image_embeddings
                    FROM events
                """))
                row = result.fetchone()
                
                return {
                    "total_events": row.total_events,
                    "text_embeddings": row.text_embeddings,
                    "image_embeddings": row.image_embeddings,
                    "text_coverage_percent": round(
                        row.text_embeddings / row.total_events * 100, 2
                    ) if row.total_events > 0 else 0,
                    "image_coverage_percent": round(
                        row.image_embeddings / row.total_events * 100, 2
                    ) if row.total_events > 0 else 0
                }
                
        except Exception as e:
            logger.error(f"Failed to get embedding stats: {e}")
            return {}
    
    async def backfill_text_embeddings(
        self,
        batch_size: int = 100,
        max_events: int = 1000
    ) -> int:
        """
        Backfill text embeddings for existing events that don't have them.
        
        Args:
            batch_size: Events to process per batch
            max_events: Maximum events to process in one run
        
        Returns:
            Number of events updated
        """
        try:
            updated = 0
            
            async with AsyncSessionLocal() as db:
                # Get events without text embeddings
                result = await db.execute(text("""
                    SELECT id, summary, event_type, severity
                    FROM events
                    WHERE text_embedding IS NULL
                        AND summary IS NOT NULL
                    ORDER BY timestamp DESC
                    LIMIT :limit
                """), {"limit": max_events})
                
                events = result.fetchall()
                logger.info(f"Backfilling text embeddings for {len(events)} events...")
                
                for i in range(0, len(events), batch_size):
                    batch = events[i:i + batch_size]
                    
                    for event in batch:
                        # Create searchable text
                        search_text = f"{event.event_type} | {event.severity} | {event.summary}"
                        
                        if await self.store_text_embedding(event.id, search_text, db):
                            updated += 1
                    
                    await db.commit()
                    logger.info(f"Processed {min(i + batch_size, len(events))}/{len(events)} events")
            
            logger.info(f"✅ Backfilled {updated} text embeddings")
            return updated
            
        except Exception as e:
            logger.error(f"Backfill failed: {e}")
            return 0


# Singleton instance
_pgvector_service: Optional[PgVectorEmbeddingService] = None


def get_pgvector_service() -> PgVectorEmbeddingService:
    """Get the singleton pgvector embedding service instance."""
    global _pgvector_service
    if _pgvector_service is None:
        _pgvector_service = PgVectorEmbeddingService()
    return _pgvector_service
