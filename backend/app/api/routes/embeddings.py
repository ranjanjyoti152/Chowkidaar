"""
Chowkidaar NVR - Embeddings API Routes
Provides embedding visualization data for the Insights page
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta
import numpy as np
from loguru import logger

from app.core.database import get_db
from app.models.user import User
from app.models.event import Event
from app.models.camera import Camera
from app.api.deps import get_current_user
from app.services.embedding_service import get_embedding_service

router = APIRouter(prefix="/embeddings", tags=["Embeddings"])


@router.get("/graph")
async def get_embedding_graph(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    days: int = Query(7, ge=1, le=30, description="Number of days to include"),
    camera_id: Optional[int] = None,
    event_type: Optional[str] = None,
    limit: int = Query(100, ge=10, le=500, description="Max events to include")
):
    """
    Get events as graph nodes with 2D positions based on embedding similarity.
    Uses t-SNE dimensionality reduction for positioning.
    """
    embedding_service = get_embedding_service()
    
    if not embedding_service.is_available():
        raise HTTPException(
            status_code=503,
            detail="Embedding service not available"
        )
    
    # Get recent events with summaries
    start_date = datetime.utcnow() - timedelta(days=days)
    
    query = (
        select(Event, Camera.name.label("camera_name"))
        .join(Camera, Event.camera_id == Camera.id)
        .where(Event.user_id == current_user.id)
        .where(Event.timestamp >= start_date)
        .where(Event.summary.isnot(None))
    )
    
    if camera_id:
        query = query.where(Event.camera_id == camera_id)
    if event_type:
        query = query.where(Event.event_type == event_type)
    
    query = query.order_by(Event.timestamp.desc()).limit(limit)
    
    result = await db.execute(query)
    rows = result.all()
    
    if not rows:
        return {"nodes": [], "links": [], "clusters": []}
    
    # Collect event data and embeddings
    events_data = []
    event_ids = []
    embeddings = []
    
    for row in rows:
        event = row[0]
        camera_name = row[1]
        event_ids.append(event.id)
        
        # Get embedding from service
        if event.id in embedding_service.event_embeddings:
            emb = embedding_service.event_embeddings[event.id]
            embeddings.append(emb)
        else:
            # Create embedding on the fly
            event_data = {
                "summary": event.summary,
                "event_type": event.event_type.value,
                "camera_name": camera_name,
                "detected_objects": event.detected_objects or []
            }
            text = embedding_service.create_event_text(event_data)
            emb = embedding_service.encode(text)
            embeddings.append(emb)
        
        events_data.append({
            "id": event.id,
            "event_type": event.event_type.value,
            "severity": event.severity.value,
            "timestamp": event.timestamp.isoformat(),
            "summary": event.summary[:200] if event.summary else "",
            "camera_id": event.camera_id,
            "camera_name": camera_name,
            "thumbnail_path": event.thumbnail_path,
            "detected_objects": event.detected_objects or []
        })
    
    if len(embeddings) < 2:
        # Not enough for visualization
        return {
            "nodes": [{"id": e["id"], "x": 0, "y": 0, **e} for e in events_data],
            "links": [],
            "clusters": []
        }
    
    # Convert to numpy array
    embeddings_array = np.array(embeddings)
    
    # Apply dimensionality reduction (t-SNE or PCA)
    try:
        from sklearn.manifold import TSNE
        from sklearn.cluster import KMeans
        
        # Use t-SNE for 2D projection
        n_samples = len(embeddings_array)
        perplexity = min(30, max(5, n_samples - 1))
        
        tsne = TSNE(n_components=2, perplexity=perplexity, random_state=42, n_iter=500)
        positions = tsne.fit_transform(embeddings_array)
        
        # Normalize to 0-1000 range for visualization
        positions = positions - positions.min(axis=0)
        positions = positions / (positions.max(axis=0) + 1e-6) * 800 + 100
        
        # Cluster events
        n_clusters = min(5, max(2, n_samples // 10))
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        cluster_labels = kmeans.fit_predict(embeddings_array)
        
    except ImportError:
        # Fallback to simple PCA-like projection
        from sklearn.decomposition import PCA
        pca = PCA(n_components=2)
        positions = pca.fit_transform(embeddings_array)
        positions = positions - positions.min(axis=0)
        positions = positions / (positions.max(axis=0) + 1e-6) * 800 + 100
        cluster_labels = [0] * len(events_data)
    except Exception as e:
        logger.warning(f"Dimensionality reduction failed: {e}")
        # Random positions as fallback
        positions = np.random.rand(len(events_data), 2) * 800 + 100
        cluster_labels = [0] * len(events_data)
    
    # Build nodes with positions
    nodes = []
    for i, event in enumerate(events_data):
        nodes.append({
            **event,
            "x": float(positions[i][0]),
            "y": float(positions[i][1]),
            "cluster": int(cluster_labels[i])
        })
    
    # Calculate similarity links (connect similar events)
    links = []
    similarity_threshold = 0.6
    
    for i in range(len(embeddings)):
        for j in range(i + 1, len(embeddings)):
            # Cosine similarity
            sim = np.dot(embeddings[i], embeddings[j]) / (
                np.linalg.norm(embeddings[i]) * np.linalg.norm(embeddings[j]) + 1e-6
            )
            if sim > similarity_threshold:
                links.append({
                    "source": event_ids[i],
                    "target": event_ids[j],
                    "value": float(sim)
                })
    
    # Build cluster info
    clusters = []
    for c in range(max(cluster_labels) + 1):
        cluster_events = [events_data[i] for i, l in enumerate(cluster_labels) if l == c]
        if cluster_events:
            # Get dominant event type in cluster
            event_types = [e["event_type"] for e in cluster_events]
            dominant_type = max(set(event_types), key=event_types.count)
            
            clusters.append({
                "id": c,
                "size": len(cluster_events),
                "dominant_type": dominant_type,
                "event_ids": [e["id"] for e in cluster_events]
            })
    
    return {
        "nodes": nodes,
        "links": links,
        "clusters": clusters,
        "total_events": len(nodes)
    }


@router.get("/stats")
async def get_embedding_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get embedding index statistics"""
    embedding_service = get_embedding_service()
    
    # Count events with embeddings
    total_indexed = len(embedding_service.event_embeddings)
    
    # Get event type distribution
    query = (
        select(Event.event_type, func.count(Event.id))
        .where(Event.user_id == current_user.id)
        .where(Event.summary.isnot(None))
        .group_by(Event.event_type)
    )
    result = await db.execute(query)
    type_counts = {str(row[0].value): row[1] for row in result.all()}
    
    # Get camera distribution
    camera_query = (
        select(Camera.name, func.count(Event.id))
        .join(Event, Event.camera_id == Camera.id)
        .where(Event.user_id == current_user.id)
        .where(Event.summary.isnot(None))
        .group_by(Camera.name)
    )
    camera_result = await db.execute(camera_query)
    camera_counts = {row[0]: row[1] for row in camera_result.all()}
    
    return {
        "total_indexed": total_indexed,
        "embedding_dimension": 384,  # all-MiniLM-L6-v2
        "model": "all-MiniLM-L6-v2",
        "event_type_distribution": type_counts,
        "camera_distribution": camera_counts,
        "is_available": embedding_service.is_available()
    }


@router.get("/similar/{event_id}")
async def get_similar_events(
    event_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(10, ge=1, le=50)
):
    """Find events similar to a given event"""
    embedding_service = get_embedding_service()
    
    if not embedding_service.is_available():
        raise HTTPException(status_code=503, detail="Embedding service not available")
    
    # Get the source event
    query = (
        select(Event, Camera.name.label("camera_name"))
        .join(Camera, Event.camera_id == Camera.id)
        .where(Event.id == event_id)
        .where(Event.user_id == current_user.id)
    )
    result = await db.execute(query)
    row = result.first()
    
    if not row:
        raise HTTPException(status_code=404, detail="Event not found")
    
    event = row[0]
    camera_name = row[1]
    
    # Search for similar events using the summary
    if event.summary:
        results = embedding_service.search(
            query=event.summary,
            top_k=limit + 1,
            min_score=0.3
        )
        
        # Filter out the source event
        similar_ids = [r[0] for r in results if r[0] != event_id][:limit]
        
        if similar_ids:
            # Fetch event details
            events_query = (
                select(Event, Camera.name.label("camera_name"))
                .join(Camera, Event.camera_id == Camera.id)
                .where(Event.id.in_(similar_ids))
                .where(Event.user_id == current_user.id)
            )
            events_result = await db.execute(events_query)
            events_rows = events_result.all()
            
            # Build response with scores
            score_map = {r[0]: r[1] for r in results}
            similar_events = []
            
            for row in events_rows:
                evt = row[0]
                cam_name = row[1]
                similar_events.append({
                    "id": evt.id,
                    "event_type": evt.event_type.value,
                    "severity": evt.severity.value,
                    "timestamp": evt.timestamp.isoformat(),
                    "summary": evt.summary,
                    "camera_name": cam_name,
                    "thumbnail_path": evt.thumbnail_path,
                    "similarity_score": score_map.get(evt.id, 0)
                })
            
            # Sort by similarity
            similar_events.sort(key=lambda x: x["similarity_score"], reverse=True)
            
            return {
                "source_event": {
                    "id": event.id,
                    "summary": event.summary,
                    "event_type": event.event_type.value
                },
                "similar_events": similar_events
            }
    
    return {"source_event": {"id": event_id}, "similar_events": []}
