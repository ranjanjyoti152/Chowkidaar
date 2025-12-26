"""
Chowkidaar NVR - AI Assistant Routes
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta

from app.core.database import get_db
from app.models.user import User
from app.models.event import Event
from app.models.chat import ChatSession, ChatMessage
from app.models.settings import UserSettings
from app.schemas.chat import (
    ChatRequest, ChatResponse, ChatSessionCreate, ChatSessionResponse,
    ChatMessageResponse, AssistantQuery, RelatedEventInfo
)
from app.models.camera import Camera
from app.api.deps import get_current_user
from app.services.vlm_service import get_unified_vlm_service
from app.services.embedding_service import get_embedding_service

router = APIRouter(prefix="/assistant", tags=["AI Assistant"])


async def configure_vlm_from_settings(user_id: int, db: AsyncSession):
    """Configure VLM service from user settings"""
    result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == user_id)
    )
    settings = result.scalar_one_or_none()
    
    vlm_service = get_unified_vlm_service()
    
    if settings:
        # Configure based on selected provider
        provider = settings.vlm_provider or "ollama"
        
        vlm_service.configure(
            provider=provider,
            ollama_url=settings.vlm_url or "http://localhost:11434",
            ollama_model=settings.vlm_model or "gemma3:4b",
            openai_api_key=getattr(settings, 'openai_api_key', None),
            openai_model=getattr(settings, 'openai_model', 'gpt-4o'),
            openai_base_url=getattr(settings, 'openai_base_url', None),
            gemini_api_key=getattr(settings, 'gemini_api_key', None),
            gemini_model=getattr(settings, 'gemini_model', 'gemini-2.0-flash-exp')
        )
    
    return vlm_service


@router.post("/chat", response_model=ChatResponse)
async def chat_with_assistant(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Chat with the AI assistant"""
    # Configure VLM from user settings
    vlm_service = await configure_vlm_from_settings(current_user.id, db)
    
    # Get or create session
    if request.session_id:
        result = await db.execute(
            select(ChatSession)
            .where(ChatSession.id == request.session_id)
            .where(ChatSession.user_id == current_user.id)
        )
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
    else:
        session = ChatSession(
            user_id=current_user.id,
            title=request.message[:50] + "..." if len(request.message) > 50 else request.message
        )
        db.add(session)
        await db.flush()
    
    # Build context from events if requested
    context = ""
    related_events = []
    events_with_images = []
    
    if request.include_events_context:
        # Get recent events for context
        if request.event_ids:
            events_query = (
                select(Event, Camera.name.label("camera_name"))
                .join(Camera, Event.camera_id == Camera.id)
                .where(Event.user_id == current_user.id)
                .where(Event.id.in_(request.event_ids))
            )
        else:
            # Get last 10 events with summaries
            events_query = (
                select(Event, Camera.name.label("camera_name"))
                .join(Camera, Event.camera_id == Camera.id)
                .where(Event.user_id == current_user.id)
                .where(Event.summary.isnot(None))
                .order_by(Event.timestamp.desc())
                .limit(10)
            )
        
        result = await db.execute(events_query)
        rows = result.all()
        
        if rows:
            context_parts = []
            for row in rows:
                event = row[0]
                camera_name = row[1]
                context_parts.append(
                    f"- [{event.timestamp.strftime('%Y-%m-%d %H:%M')}] "
                    f"{event.event_type.value}: {event.summary}"
                )
                related_events.append(event.id)
                
                # Add event with image info
                events_with_images.append(RelatedEventInfo(
                    id=event.id,
                    event_type=event.event_type.value,
                    severity=event.severity.value,
                    timestamp=event.timestamp,
                    summary=event.summary,
                    frame_path=event.frame_path,
                    thumbnail_path=event.thumbnail_path,
                    camera_name=camera_name,
                    detected_objects=event.detected_objects or []
                ))
            context = "\n".join(context_parts)
    
    # Get chat history
    history = []
    if request.session_id:
        result = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session.id)
            .order_by(ChatMessage.created_at)
            .limit(20)
        )
        messages = result.scalars().all()
        history = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]
    
    # Check if user is asking about images
    image_keywords = ['image', 'photo', 'picture', 'show', 'dikhao', 'dikha', 'frame', 'snapshot', 'footage', 'recording', 'see', 'dekho', 'dekh']
    asking_for_images = any(kw in request.message.lower() for kw in image_keywords)
    
    # Get response from VLM
    response = await vlm_service.chat(
        message=request.message,
        context=context if context else None,
        history=history if history else None,
        has_images=bool(events_with_images) or asking_for_images
    )
    
    # Save user message
    user_message = ChatMessage(
        session_id=session.id,
        role="user",
        content=request.message
    )
    db.add(user_message)
    
    # Save assistant response
    assistant_message = ChatMessage(
        session_id=session.id,
        role="assistant",
        content=response,
        message_metadata={"related_events": related_events}
    )
    db.add(assistant_message)
    
    await db.commit()
    
    # Only return images if user asked for them
    return ChatResponse(
        message=response,
        session_id=session.id,
        related_events=related_events if asking_for_images else [],
        events_with_images=events_with_images[:4] if asking_for_images else [],  # Max 4 images
        metadata={}
    )


@router.get("/sessions", response_model=List[ChatSessionResponse])
async def list_chat_sessions(
    skip: int = 0,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List chat sessions"""
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == current_user.id)
        .order_by(ChatSession.updated_at.desc())
        .offset(skip)
        .limit(limit)
    )
    sessions = result.scalars().all()
    
    return sessions


@router.get("/sessions/{session_id}", response_model=ChatSessionResponse)
async def get_chat_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific chat session with messages"""
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.id == session_id)
        .where(ChatSession.user_id == current_user.id)
    )
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    return session


@router.delete("/sessions/{session_id}")
async def delete_chat_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a chat session"""
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.id == session_id)
        .where(ChatSession.user_id == current_user.id)
    )
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    await db.delete(session)
    await db.commit()
    
    return {"message": "Session deleted successfully"}


@router.post("/query", response_model=ChatResponse)
async def query_events(
    query: AssistantQuery,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Query events using natural language"""
    # Configure VLM from user settings
    vlm_service = await configure_vlm_from_settings(current_user.id, db)
    
    # Build events query with camera join
    events_query = (
        select(Event, Camera.name.label("camera_name"))
        .join(Camera, Event.camera_id == Camera.id)
        .where(Event.user_id == current_user.id)
    )
    
    # Apply filters if provided
    if query.filters:
        if "camera_id" in query.filters:
            events_query = events_query.where(
                Event.camera_id == query.filters["camera_id"]
            )
        if "event_type" in query.filters:
            events_query = events_query.where(
                Event.event_type == query.filters["event_type"]
            )
        if "start_date" in query.filters:
            events_query = events_query.where(
                Event.timestamp >= query.filters["start_date"]
            )
        if "end_date" in query.filters:
            events_query = events_query.where(
                Event.timestamp <= query.filters["end_date"]
            )
    
    events_query = events_query.order_by(Event.timestamp.desc()).limit(query.limit)
    
    result = await db.execute(events_query)
    rows = result.all()
    
    if not rows:
        return ChatResponse(
            message="No events found matching your query criteria.",
            session_id=0,
            related_events=[],
            events_with_images=[],
            metadata={}
        )
    
    # Build events summary
    events_summary = []
    related_events = []
    events_with_images = []
    
    for row in rows:
        event = row[0]
        camera_name = row[1]
        
        events_summary.append(
            f"Event #{event.id} [{event.timestamp.strftime('%Y-%m-%d %H:%M')}]\n"
            f"Camera: {camera_name}\n"
            f"Type: {event.event_type.value}\n"
            f"Severity: {event.severity.value}\n"
            f"Summary: {event.summary or 'No summary available'}\n"
        )
        related_events.append(event.id)
        
        # Add event with image info
        events_with_images.append(RelatedEventInfo(
            id=event.id,
            event_type=event.event_type.value,
            severity=event.severity.value,
            timestamp=event.timestamp,
            summary=event.summary,
            frame_path=event.frame_path,
            thumbnail_path=event.thumbnail_path,
            camera_name=camera_name,
            detected_objects=event.detected_objects or []
        ))
    
    events_text = "\n---\n".join(events_summary)
    
    # Analyze events with VLM
    response = await vlm_service.analyze_events(
        events_summary=events_text,
        query=query.query,
        has_images=bool(events_with_images)
    )
    
    return ChatResponse(
        message=response,
        session_id=0,
        related_events=related_events,
        events_with_images=events_with_images,
        metadata={"events_count": len(rows)}
    )


@router.get("/suggestions")
async def get_query_suggestions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get suggested queries based on recent events"""
    # Get recent event types
    result = await db.execute(
        select(Event.event_type)
        .where(Event.user_id == current_user.id)
        .order_by(Event.timestamp.desc())
        .limit(50)
    )
    event_types = set(row[0].value for row in result.all())
    
    suggestions = [
        "What happened in the last hour?",
        "Show me a summary of today's events",
        "Were there any critical incidents this week?",
    ]
    
    if "person_detected" in event_types:
        suggestions.append("How many people were detected today?")
    if "vehicle_detected" in event_types:
        suggestions.append("Show me all vehicle detections")
    if "fire_detected" in event_types or "smoke_detected" in event_types:
        suggestions.append("Were there any fire or smoke alerts?")
    
    return {"suggestions": suggestions}


@router.post("/semantic-search")
async def semantic_search_events(
    query: str,
    camera_id: Optional[int] = None,
    camera_name: Optional[str] = None,
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Search events using semantic similarity (vector embeddings).
    Finds events based on meaning, not just keywords.
    """
    embedding_service = get_embedding_service()
    
    if not embedding_service.is_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Embedding service not available. Install sentence-transformers."
        )
    
    # Perform semantic search
    results = embedding_service.search(
        query=query,
        camera_id=camera_id,
        camera_name=camera_name,
        top_k=limit,
        min_score=0.3
    )
    
    if not results:
        return {
            "query": query,
            "events": [],
            "message": "No matching events found"
        }
    
    # Fetch full event details from database
    event_ids = [r[0] for r in results]
    events_query = (
        select(Event, Camera.name.label("camera_name"))
        .join(Camera, Event.camera_id == Camera.id)
        .where(Event.id.in_(event_ids))
        .where(Event.user_id == current_user.id)
    )
    result = await db.execute(events_query)
    rows = result.all()
    
    # Build response with similarity scores
    events_map = {row[0].id: (row[0], row[1]) for row in rows}
    
    events = []
    for event_id, score, metadata in results:
        if event_id in events_map:
            event, camera_name = events_map[event_id]
            events.append({
                "id": event.id,
                "camera_id": event.camera_id,
                "camera_name": camera_name,
                "event_type": event.event_type.value,
                "severity": event.severity.value,
                "timestamp": event.timestamp.isoformat(),
                "summary": event.summary,
                "similarity_score": round(score, 3),
                "thumbnail_path": event.thumbnail_path
            })
    
    return {
        "query": query,
        "events": events,
        "total_indexed": len(embedding_service.event_embeddings)
    }


@router.get("/camera/{camera_id}/summary")
async def get_camera_events_summary(
    camera_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get intelligent summary of events for a specific camera.
    Uses vector embeddings and VLM for analysis.
    """
    # Verify camera exists and belongs to user
    camera_result = await db.execute(
        select(Camera).where(Camera.id == camera_id).where(Camera.owner_id == current_user.id)
    )
    camera = camera_result.scalar_one_or_none()
    
    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera not found"
        )
    
    embedding_service = get_embedding_service()
    
    # Get camera statistics from embeddings
    stats = embedding_service.get_camera_summary(camera_id=camera_id)
    
    # Get recent events from database for detailed summary
    events_result = await db.execute(
        select(Event)
        .where(Event.camera_id == camera_id)
        .where(Event.user_id == current_user.id)
        .where(Event.summary.isnot(None))
        .order_by(Event.timestamp.desc())
        .limit(20)
    )
    recent_events = events_result.scalars().all()
    
    # Build context for VLM
    if recent_events:
        vlm_service = await configure_vlm_from_settings(current_user.id, db)
        
        events_text = "\n".join([
            f"- [{e.timestamp.strftime('%Y-%m-%d %H:%M')}] {e.event_type.value}: {e.summary}"
            for e in recent_events
        ])
        
        # Generate intelligent summary
        prompt = f"""Analyze these events from camera "{camera.name}" and provide:
1. A brief summary of what typically happens at this location
2. Any patterns or unusual activities
3. Overall activity level (low/medium/high)

Events:
{events_text}

Provide a concise analysis in 2-3 sentences."""

        analysis = await vlm_service.chat(
            message=prompt,
            context=None,
            history=None,
            has_images=False
        )
    else:
        analysis = "No events recorded for this camera yet."
    
    return {
        "camera_id": camera_id,
        "camera_name": camera.name,
        "total_events": stats.get('total_events', 0),
        "event_types": stats.get('event_types', {}),
        "severity_breakdown": stats.get('severity_counts', {}),
        "recent_events": [
            {
                "id": e['id'],
                "summary": e['summary'],
                "timestamp": e['timestamp'].isoformat() if e.get('timestamp') else None
            }
            for e in stats.get('recent_events', [])
        ],
        "ai_analysis": analysis
    }


@router.post("/smart-chat")
async def smart_chat_with_context(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Enhanced chat with automatic semantic event retrieval.
    Finds relevant events based on the user's question.
    """
    vlm_service = await configure_vlm_from_settings(current_user.id, db)
    embedding_service = get_embedding_service()
    
    # Get or create session
    if request.session_id:
        result = await db.execute(
            select(ChatSession)
            .where(ChatSession.id == request.session_id)
            .where(ChatSession.user_id == current_user.id)
        )
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
    else:
        session = ChatSession(
            user_id=current_user.id,
            title=request.message[:50] + "..." if len(request.message) > 50 else request.message
        )
        db.add(session)
        await db.flush()
    
    # Extract camera name from query if mentioned
    camera_filter = None
    message_lower = request.message.lower()
    
    # Get all cameras to check for name mentions
    cameras_result = await db.execute(
        select(Camera).where(Camera.owner_id == current_user.id)
    )
    cameras = cameras_result.scalars().all()
    
    for camera in cameras:
        if camera.name.lower() in message_lower:
            camera_filter = camera.id
            break
    
    # Use semantic search to find relevant events
    context = ""
    related_events = []
    events_with_images = []
    
    if embedding_service.is_available() and embedding_service.event_embeddings:
        search_results = embedding_service.search(
            query=request.message,
            camera_id=camera_filter,
            top_k=5,
            min_score=0.35
        )
        
        if search_results:
            # Fetch full events
            event_ids = [r[0] for r in search_results]
            events_query = (
                select(Event, Camera.name.label("camera_name"))
                .join(Camera, Event.camera_id == Camera.id)
                .where(Event.id.in_(event_ids))
                .where(Event.user_id == current_user.id)
            )
            result = await db.execute(events_query)
            rows = result.all()
            
            events_map = {row[0].id: (row[0], row[1]) for row in rows}
            
            context_parts = []
            for event_id, score, metadata in search_results:
                if event_id in events_map:
                    event, camera_name = events_map[event_id]
                    context_parts.append(
                        f"- [{event.timestamp.strftime('%Y-%m-%d %H:%M')}] "
                        f"Camera: {camera_name} | {event.event_type.value}: {event.summary} "
                        f"(relevance: {score:.0%})"
                    )
                    related_events.append(event.id)
                    
                    events_with_images.append(RelatedEventInfo(
                        id=event.id,
                        event_type=event.event_type.value,
                        severity=event.severity.value,
                        timestamp=event.timestamp,
                        summary=event.summary,
                        frame_path=event.frame_path,
                        thumbnail_path=event.thumbnail_path,
                        camera_name=camera_name,
                        detected_objects=event.detected_objects or []
                    ))
            
            context = "Relevant events found:\n" + "\n".join(context_parts)
    
    # Fallback to regular database query if no semantic results
    if not context and request.include_events_context:
        events_query = (
            select(Event, Camera.name.label("camera_name"))
            .join(Camera, Event.camera_id == Camera.id)
            .where(Event.user_id == current_user.id)
            .where(Event.summary.isnot(None))
            .order_by(Event.timestamp.desc())
            .limit(10)
        )
        if camera_filter:
            events_query = events_query.where(Event.camera_id == camera_filter)
        
        result = await db.execute(events_query)
        rows = result.all()
        
        if rows:
            context_parts = []
            for row in rows:
                event = row[0]
                camera_name = row[1]
                context_parts.append(
                    f"- [{event.timestamp.strftime('%Y-%m-%d %H:%M')}] "
                    f"Camera: {camera_name} | {event.event_type.value}: {event.summary}"
                )
                related_events.append(event.id)
                
                events_with_images.append(RelatedEventInfo(
                    id=event.id,
                    event_type=event.event_type.value,
                    severity=event.severity.value,
                    timestamp=event.timestamp,
                    summary=event.summary,
                    frame_path=event.frame_path,
                    thumbnail_path=event.thumbnail_path,
                    camera_name=camera_name,
                    detected_objects=event.detected_objects or []
                ))
            context = "Recent events:\n" + "\n".join(context_parts)
    
    # Get chat history
    history = []
    if request.session_id:
        result = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session.id)
            .order_by(ChatMessage.created_at)
            .limit(20)
        )
        messages = result.scalars().all()
        history = [{"role": msg.role, "content": msg.content} for msg in messages]
    
    # Get response from VLM
    response = await vlm_service.chat(
        message=request.message,
        context=context if context else None,
        history=history if history else None,
        has_images=bool(events_with_images)
    )
    
    # Save messages
    user_message = ChatMessage(session_id=session.id, role="user", content=request.message)
    db.add(user_message)
    
    assistant_message = ChatMessage(
        session_id=session.id,
        role="assistant",
        content=response,
        message_metadata={"related_events": related_events, "semantic_search": True}
    )
    db.add(assistant_message)
    
    await db.commit()
    
    return ChatResponse(
        message=response,
        session_id=session.id,
        related_events=related_events,
        events_with_images=events_with_images[:4],
        metadata={"semantic_search_used": bool(context and "relevance:" in context)}
    )
