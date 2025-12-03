"""
Chowkidaar NVR - Events Routes
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from datetime import datetime, timedelta
from pathlib import Path

from app.core.database import get_db
from app.models.user import User
from app.models.camera import Camera
from app.models.event import Event, EventType, EventSeverity
from app.schemas.event import (
    EventResponse, EventWithCamera, EventUpdate, EventFilter,
    EventStats, EventSummaryRequest
)
from app.api.deps import get_current_user
from app.services.event_processor import get_event_processor

router = APIRouter(prefix="/events", tags=["Events"])


@router.get("", response_model=List[EventWithCamera])
async def list_events(
    camera_id: Optional[int] = None,
    event_type: Optional[EventType] = None,
    severity: Optional[EventSeverity] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    is_acknowledged: Optional[bool] = None,
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List events with filters"""
    query = (
        select(Event, Camera.name, Camera.location)
        .join(Camera)
        .where(Event.user_id == current_user.id)
    )
    
    # Apply filters
    if camera_id:
        query = query.where(Event.camera_id == camera_id)
    if event_type:
        query = query.where(Event.event_type == event_type)
    if severity:
        query = query.where(Event.severity == severity)
    if start_date:
        query = query.where(Event.timestamp >= start_date)
    if end_date:
        query = query.where(Event.timestamp <= end_date)
    if is_acknowledged is not None:
        query = query.where(Event.is_acknowledged == is_acknowledged)
    
    query = query.order_by(Event.timestamp.desc()).offset(skip).limit(limit)
    
    result = await db.execute(query)
    rows = result.all()
    
    events_with_camera = []
    for event, camera_name, camera_location in rows:
        event_dict = EventResponse.model_validate(event).model_dump()
        event_dict["camera_name"] = camera_name
        event_dict["camera_location"] = camera_location
        events_with_camera.append(EventWithCamera(**event_dict))
    
    return events_with_camera


@router.get("/stats", response_model=EventStats)
async def get_event_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get event statistics"""
    now = datetime.utcnow()
    today = now.date()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)
    
    # Total events
    total_result = await db.execute(
        select(func.count(Event.id))
        .where(Event.user_id == current_user.id)
    )
    total_events = total_result.scalar() or 0
    
    # Events by type
    type_result = await db.execute(
        select(Event.event_type, func.count(Event.id))
        .where(Event.user_id == current_user.id)
        .group_by(Event.event_type)
    )
    events_by_type = {str(row[0].value): row[1] for row in type_result.all()}
    
    # Events by severity
    severity_result = await db.execute(
        select(Event.severity, func.count(Event.id))
        .where(Event.user_id == current_user.id)
        .group_by(Event.severity)
    )
    events_by_severity = {str(row[0].value): row[1] for row in severity_result.all()}
    
    # Events by camera
    camera_result = await db.execute(
        select(Camera.name, func.count(Event.id))
        .join(Camera)
        .where(Event.user_id == current_user.id)
        .group_by(Camera.name)
    )
    events_by_camera = {row[0]: row[1] for row in camera_result.all()}
    
    # Events today
    today_result = await db.execute(
        select(func.count(Event.id))
        .where(Event.user_id == current_user.id)
        .where(func.date(Event.timestamp) == today)
    )
    events_today = today_result.scalar() or 0
    
    # Events this week
    week_result = await db.execute(
        select(func.count(Event.id))
        .where(Event.user_id == current_user.id)
        .where(Event.timestamp >= week_ago)
    )
    events_this_week = week_result.scalar() or 0
    
    # Events this month
    month_result = await db.execute(
        select(func.count(Event.id))
        .where(Event.user_id == current_user.id)
        .where(Event.timestamp >= month_ago)
    )
    events_this_month = month_result.scalar() or 0
    
    return EventStats(
        total_events=total_events,
        events_by_type=events_by_type,
        events_by_severity=events_by_severity,
        events_by_camera=events_by_camera,
        events_today=events_today,
        events_this_week=events_this_week,
        events_this_month=events_this_month
    )


@router.get("/{event_id}", response_model=EventWithCamera)
async def get_event(
    event_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get event by ID"""
    result = await db.execute(
        select(Event, Camera.name, Camera.location)
        .join(Camera)
        .where(Event.id == event_id)
        .where(Event.user_id == current_user.id)
    )
    row = result.one_or_none()
    
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )
    
    event, camera_name, camera_location = row
    event_dict = EventResponse.model_validate(event).model_dump()
    event_dict["camera_name"] = camera_name
    event_dict["camera_location"] = camera_location
    
    return EventWithCamera(**event_dict)


@router.put("/{event_id}", response_model=EventResponse)
async def update_event(
    event_id: int,
    event_update: EventUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update event (acknowledge, add notes)"""
    result = await db.execute(
        select(Event)
        .where(Event.id == event_id)
        .where(Event.user_id == current_user.id)
    )
    event = result.scalar_one_or_none()
    
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )
    
    update_data = event_update.model_dump(exclude_unset=True)
    
    if update_data.get("is_acknowledged") and not event.is_acknowledged:
        update_data["acknowledged_at"] = datetime.utcnow()
        update_data["acknowledged_by"] = current_user.id
    
    for key, value in update_data.items():
        setattr(event, key, value)
    
    await db.commit()
    await db.refresh(event)
    
    return event


@router.delete("/{event_id}")
async def delete_event(
    event_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete an event"""
    result = await db.execute(
        select(Event)
        .where(Event.id == event_id)
        .where(Event.user_id == current_user.id)
    )
    event = result.scalar_one_or_none()
    
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )
    
    # Delete associated files
    if event.frame_path:
        path = Path(event.frame_path)
        if path.exists():
            path.unlink()
    if event.thumbnail_path:
        path = Path(event.thumbnail_path)
        if path.exists():
            path.unlink()
    
    await db.delete(event)
    await db.commit()
    
    return {"message": "Event deleted successfully"}


@router.get("/{event_id}/frame")
async def get_event_frame(
    event_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get event frame image"""
    result = await db.execute(
        select(Event)
        .where(Event.id == event_id)
        .where(Event.user_id == current_user.id)
    )
    event = result.scalar_one_or_none()
    
    if not event or not event.frame_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event frame not found"
        )
    
    path = Path(event.frame_path)
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Frame file not found"
        )
    
    return FileResponse(path, media_type="image/jpeg")


@router.get("/{event_id}/thumbnail")
async def get_event_thumbnail(
    event_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get event thumbnail image"""
    result = await db.execute(
        select(Event)
        .where(Event.id == event_id)
        .where(Event.user_id == current_user.id)
    )
    event = result.scalar_one_or_none()
    
    if not event or not event.thumbnail_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event thumbnail not found"
        )
    
    path = Path(event.thumbnail_path)
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Thumbnail file not found"
        )
    
    return FileResponse(path, media_type="image/jpeg")


@router.post("/{event_id}/regenerate-summary", response_model=EventResponse)
async def regenerate_event_summary(
    event_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Regenerate VLM summary for an event"""
    result = await db.execute(
        select(Event, Camera.name)
        .join(Camera)
        .where(Event.id == event_id)
        .where(Event.user_id == current_user.id)
    )
    row = result.one_or_none()
    
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )
    
    event, camera_name = row
    
    if not event.frame_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Event has no associated frame"
        )
    
    processor = await get_event_processor()
    summary = await processor.regenerate_summary(
        frame_path=event.frame_path,
        event_type=event.event_type.value,
        detected_objects=event.detected_objects.get("objects", []),
        camera_name=camera_name,
        timestamp=event.timestamp
    )
    
    if summary:
        event.summary = summary
        event.summary_generated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(event)
    
    return event


@router.post("/acknowledge-all")
async def acknowledge_all_events(
    camera_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Acknowledge all unacknowledged events"""
    from sqlalchemy import update
    
    query = (
        update(Event)
        .where(Event.user_id == current_user.id)
        .where(Event.is_acknowledged == False)
        .values(
            is_acknowledged=True,
            acknowledged_at=datetime.utcnow(),
            acknowledged_by=current_user.id
        )
    )
    
    if camera_id:
        query = query.where(Event.camera_id == camera_id)
    
    result = await db.execute(query)
    await db.commit()
    
    return {"message": f"Acknowledged {result.rowcount} events"}
