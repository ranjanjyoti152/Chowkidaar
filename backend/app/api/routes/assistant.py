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
from app.schemas.chat import (
    ChatRequest, ChatResponse, ChatSessionCreate, ChatSessionResponse,
    ChatMessageResponse, AssistantQuery, RelatedEventInfo
)
from app.models.camera import Camera
from app.api.deps import get_current_user
from app.services.ollama_vlm import get_vlm_service

router = APIRouter(prefix="/assistant", tags=["AI Assistant"])


@router.post("/chat", response_model=ChatResponse)
async def chat_with_assistant(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Chat with the AI assistant"""
    vlm_service = await get_vlm_service()
    
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
    
    return ChatResponse(
        message=response,
        session_id=session.id,
        related_events=related_events,
        events_with_images=events_with_images,
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
    vlm_service = await get_vlm_service()
    
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
