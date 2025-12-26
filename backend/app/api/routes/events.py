"""
Chowkidaar NVR - Events Routes
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from datetime import datetime, timedelta
from pathlib import Path
from pydantic import BaseModel
from loguru import logger

from app.core.database import get_db
from app.core.config import settings
from app.models.user import User
from app.models.camera import Camera
from app.models.event import Event, EventType, EventSeverity
from app.schemas.event import (
    EventResponse, EventWithCamera, EventUpdate, EventFilter,
    EventStats, EventSummaryRequest
)
from app.api.deps import get_current_user
from app.services.event_processor import get_event_processor
from app.services.vlm_service import get_unified_vlm_service
from app.models.settings import UserSettings

router = APIRouter(prefix="/events", tags=["Events"])


class SearchRequest(BaseModel):
    query: str


@router.get("", response_model=List[EventWithCamera])
async def list_events(
    camera_id: Optional[int] = None,
    event_type: Optional[EventType] = None,
    severity: Optional[EventSeverity] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    is_acknowledged: Optional[bool] = None,
    sort_order: Optional[str] = "newest",  # newest or oldest
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List events with filters and sorting"""
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
    
    # Apply sorting
    if sort_order == "oldest":
        query = query.order_by(Event.timestamp.asc())
    else:  # default: newest first
        query = query.order_by(Event.timestamp.desc())
    
    query = query.offset(skip).limit(limit)
    
    result = await db.execute(query)
    rows = result.all()
    
    events_with_camera = []
    for event, camera_name, camera_location in rows:
        event_dict = EventResponse.model_validate(event).model_dump()
        event_dict["camera_name"] = camera_name
        event_dict["camera_location"] = camera_location
        events_with_camera.append(EventWithCamera(**event_dict))
    
    return events_with_camera


@router.post("/search", response_model=List[EventWithCamera])
async def search_events(
    request: SearchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    AI-powered semantic search for events using VLM.
    Search using natural language like:
    - "red car with black hoodie person"
    - "person talking on phone"
    - "delivery guy at door"
    """
    search_query = request.query.strip()
    if not search_query:
        raise HTTPException(status_code=400, detail="Search query cannot be empty")
    
    logger.info(f"🔍 AI Search query: '{search_query}' by user {current_user.id}")
    
    # Get user's VLM settings
    result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == current_user.id)
    )
    user_settings = result.scalar_one_or_none()
    
    if not user_settings or not user_settings.vlm_url:
        raise HTTPException(status_code=400, detail="VLM not configured. Please configure VLM in Settings.")
    
    # Get recent events with summaries (last 7 days, max 200)
    week_ago = datetime.now() - timedelta(days=7)
    events_result = await db.execute(
        select(Event, Camera.name, Camera.location)
        .join(Camera)
        .where(Event.user_id == current_user.id)
        .where(Event.timestamp >= week_ago)
        .where(Event.summary.isnot(None))
        .order_by(Event.timestamp.desc())
        .limit(200)
    )
    all_events = events_result.all()
    
    if not all_events:
        return []
    
    # Configure VLM based on provider
    vlm = get_unified_vlm_service()
    provider = getattr(user_settings, 'vlm_provider', 'ollama')
    vlm.configure(
        provider=provider,
        ollama_url=user_settings.vlm_url,
        ollama_model=user_settings.vlm_model,
        openai_api_key=getattr(user_settings, 'openai_api_key', None),
        openai_model=getattr(user_settings, 'openai_model', 'gpt-4o'),
        openai_base_url=getattr(user_settings, 'openai_base_url', None),
        gemini_api_key=getattr(user_settings, 'gemini_api_key', None),
        gemini_model=getattr(user_settings, 'gemini_model', 'gemini-2.0-flash-exp')
    )
    
    # Build event summaries for VLM analysis
    event_data = []
    for event, camera_name, camera_location in all_events:
        summary = event.summary or ""
        # Add detected objects info
        objects_info = ""
        if event.detected_objects:
            objects = [obj.get("class_name", "") for obj in event.detected_objects if isinstance(obj, dict)]
            objects_info = f" [Detected: {', '.join(objects)}]" if objects else ""
        
        event_data.append({
            "id": event.id,
            "summary": summary[:300] + objects_info,
            "event": event,
            "camera_name": camera_name,
            "camera_location": camera_location
        })
    
    # Process in batches of 30 events for better accuracy
    matched_event_ids = set()
    batch_size = 30
    
    for i in range(0, min(len(event_data), 150), batch_size):
        batch = event_data[i:i + batch_size]
        
        # Create VLM prompt
        event_list = "\n".join([
            f"ID:{e['id']} - {e['summary'][:200]}"
            for e in batch
        ])
        
        prompt = f"""You are a precise search assistant for a security camera system.

USER'S SEARCH QUERY: "{search_query}"

TASK: Find events that ACTUALLY MATCH the search query. Be STRICT - only return events that genuinely match.

EVENT LIST:
{event_list}

RULES:
1. ONLY return event IDs that TRULY match the search query
2. If query says "person wearing watch" - only match if summary mentions watch
3. If query says "red car" - only match if summary mentions red car specifically
4. DO NOT match events just because they have "person" if query asks for specific details
5. If NOTHING matches the query, return: NONE

RESPOND WITH ONLY THE MATCHING EVENT IDs (comma-separated numbers) OR "NONE":"""

        try:
            response = await vlm.chat(prompt)
            
            if response and "NONE" not in response.upper():
                # Parse event IDs
                import re
                ids = re.findall(r'\b(\d+)\b', response)
                for id_str in ids:
                    event_id = int(id_str)
                    # Verify it's a valid event ID from our batch
                    if any(e["id"] == event_id for e in batch):
                        matched_event_ids.add(event_id)
                
                logger.debug(f"VLM batch {i//batch_size + 1}: Found {len(ids)} matches")
        except Exception as e:
            logger.warning(f"VLM search batch failed: {e}")
            continue
    
    # If VLM found matches, use those
    if matched_event_ids:
        logger.info(f"✅ VLM found {len(matched_event_ids)} matching events")
        
        # Get matched events in order
        events_with_camera = []
        for ed in event_data:
            if ed["id"] in matched_event_ids:
                event = ed["event"]
                event_dict = EventResponse.model_validate(event).model_dump()
                event_dict["camera_name"] = ed["camera_name"]
                event_dict["camera_location"] = ed["camera_location"]
                events_with_camera.append(EventWithCamera(**event_dict))
        
        return events_with_camera
    
    # VLM said no matches - return empty (don't show unrelated results)
    logger.info(f"❌ No events match query: '{search_query}'")
    return []


@router.get("/stats", response_model=EventStats)
async def get_event_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get event statistics"""
    # Use local time instead of UTC for accurate "today" comparison
    now = datetime.now()
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


class HeatmapDataPoint(BaseModel):
    """Single data point in the heatmap"""
    hour: int  # 0-23
    day: str   # Date string YYYY-MM-DD
    day_name: str  # Mon, Tue, etc.
    count: int
    class_name: str


class HeatmapResponse(BaseModel):
    """Heatmap data response"""
    data: List[HeatmapDataPoint]
    available_classes: List[str]
    date_range: dict


class SpatialHeatPoint(BaseModel):
    """A single point for spatial heatmap - normalized coordinates (0-1)"""
    x: float  # Normalized x center (0-1)
    y: float  # Normalized y center (0-1)
    class_name: str
    weight: float = 1.0  # Weight/intensity


class SpatialHeatmapResponse(BaseModel):
    """Spatial heatmap data per camera"""
    camera_id: int
    points: List[SpatialHeatPoint]
    total_detections: int
    class_counts: dict
    frame_width: int = 1920
    frame_height: int = 1080


@router.get("/heatmap/spatial")
async def get_spatial_heatmap_data(
    camera_id: int = Query(..., description="Camera ID to get spatial heatmap for"),
    classes: Optional[str] = Query(None, description="Comma-separated class names to filter"),
    days: int = Query(7, ge=1, le=30, description="Number of days to include"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get spatial heatmap data with normalized bbox positions for a specific camera"""
    
    now = datetime.now()
    start_date = now - timedelta(days=days)
    
    # Parse classes filter
    class_filter = None
    if classes:
        class_filter = [c.strip().lower() for c in classes.split(",")]
    
    # Get camera resolution for proper normalization
    camera_result = await db.execute(
        select(Camera).where(Camera.id == camera_id).where(Camera.owner_id == current_user.id)
    )
    camera = camera_result.scalar_one_or_none()
    
    # Default to HD resolution if not set
    frame_width = camera.resolution_width if camera and camera.resolution_width else 1920
    frame_height = camera.resolution_height if camera and camera.resolution_height else 1080
    
    # Query events for this camera
    query = (
        select(Event)
        .where(Event.user_id == current_user.id)
        .where(Event.camera_id == camera_id)
        .where(Event.timestamp >= start_date)
        .where(Event.detected_objects.isnot(None))
    )
    
    result = await db.execute(query)
    events = result.scalars().all()
    
    # Extract bbox center points
    points = []
    class_counts = {}
    
    for event in events:
        detected_objects = event.detected_objects or []
        if isinstance(detected_objects, list):
            for obj in detected_objects:
                if isinstance(obj, dict):
                    class_name = obj.get("class", obj.get("class_name", "unknown")).lower()
                    
                    # Apply class filter
                    if class_filter and class_name not in class_filter:
                        continue
                    
                    # Get bounding box - try different formats
                    bbox = obj.get("bbox", obj.get("box", None))
                    if bbox and isinstance(bbox, (list, tuple)) and len(bbox) >= 4:
                        # bbox is [x1, y1, x2, y2] in pixel coords
                        x1, y1, x2, y2 = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
                        
                        # Calculate center point
                        cx = (x1 + x2) / 2
                        cy = (y1 + y2) / 2
                        
                        # Normalize using actual camera resolution
                        # If values are already < 1, they're already normalized
                        if cx > 1 or cy > 1:
                            cx = cx / frame_width
                            cy = cy / frame_height
                        
                        # Clamp to 0-1 range
                        cx = max(0.0, min(1.0, cx))
                        cy = max(0.0, min(1.0, cy))
                        
                        points.append(SpatialHeatPoint(
                            x=cx,
                            y=cy,
                            class_name=class_name,
                            weight=float(obj.get("confidence", 1.0))
                        ))
                        
                        class_counts[class_name] = class_counts.get(class_name, 0) + 1
    
    return SpatialHeatmapResponse(
        camera_id=camera_id,
        points=points,
        total_detections=len(points),
        class_counts=class_counts,
        frame_width=frame_width,
        frame_height=frame_height
    )



@router.get("/heatmap", response_model=HeatmapResponse)
async def get_heatmap_data(
    camera_id: Optional[int] = None,
    classes: Optional[str] = Query(None, description="Comma-separated class names to filter"),
    days: int = Query(7, ge=1, le=30, description="Number of days to include"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get heatmap data showing detection activity by hour and day, grouped by class"""
    
    # Calculate date range
    now = datetime.now()
    start_date = now - timedelta(days=days)
    
    # Parse classes filter
    class_filter = None
    if classes:
        class_filter = [c.strip().lower() for c in classes.split(",")]
    
    # Query events with detected objects
    query = (
        select(Event)
        .where(Event.user_id == current_user.id)
        .where(Event.timestamp >= start_date)
        .where(Event.detected_objects.isnot(None))
    )
    
    if camera_id:
        query = query.where(Event.camera_id == camera_id)
    
    result = await db.execute(query)
    events = result.scalars().all()
    
    # Process events into heatmap data
    heatmap_data = []
    all_classes = set()
    
    for event in events:
        event_hour = event.timestamp.hour
        event_day = event.timestamp.strftime("%Y-%m-%d")
        event_day_name = event.timestamp.strftime("%a")
        
        # Extract class names from detected_objects
        detected_objects = event.detected_objects or []
        if isinstance(detected_objects, list):
            for obj in detected_objects:
                if isinstance(obj, dict):
                    class_name = obj.get("class", obj.get("class_name", "unknown")).lower()
                    all_classes.add(class_name)
                    
                    # Apply class filter if specified
                    if class_filter and class_name not in class_filter:
                        continue
                    
                    heatmap_data.append({
                        "hour": event_hour,
                        "day": event_day,
                        "day_name": event_day_name,
                        "class_name": class_name
                    })
    
    # Aggregate counts
    from collections import Counter
    aggregated = Counter()
    for point in heatmap_data:
        key = (point["hour"], point["day"], point["day_name"], point["class_name"])
        aggregated[key] += 1
    
    # Convert to response format
    result_data = [
        HeatmapDataPoint(
            hour=key[0],
            day=key[1],
            day_name=key[2],
            class_name=key[3],
            count=count
        )
        for key, count in aggregated.items()
    ]
    
    return HeatmapResponse(
        data=result_data,
        available_classes=sorted(list(all_classes)),
        date_range={
            "start": start_date.strftime("%Y-%m-%d"),
            "end": now.strftime("%Y-%m-%d"),
            "days": days
        }
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
    
    # Get frame path from database
    frame_path = event.frame_path
    path = Path(frame_path)
    
    # If absolute path exists, use it directly
    if path.is_absolute() and path.exists():
        return FileResponse(path, media_type="image/jpeg")
    
    # Extract filename
    filename = Path(frame_path).name
    
    # Try storage path from config
    config_path = Path(settings.frames_storage_path) / filename
    if config_path.exists():
        return FileResponse(config_path, media_type="image/jpeg")
    
    # Try base path + storage
    base_storage = Path(settings.base_path) / "storage" / "frames" / filename
    if base_storage.exists():
        return FileResponse(base_storage, media_type="image/jpeg")
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Frame file not found: {filename}"
    )


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
    
    # Get thumbnail path
    thumb_path = event.thumbnail_path
    path = Path(thumb_path)
    
    # If absolute path exists, use it directly
    if path.is_absolute() and path.exists():
        return FileResponse(path, media_type="image/jpeg")
    
    # Extract filename
    filename = Path(thumb_path).name
    
    # Try storage path from config
    config_path = Path(settings.frames_storage_path) / filename
    if config_path.exists():
        return FileResponse(config_path, media_type="image/jpeg")
    
    # Try base path + storage
    base_storage = Path(settings.base_path) / "storage" / "frames" / filename
    if base_storage.exists():
        return FileResponse(base_storage, media_type="image/jpeg")
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Thumbnail file not found: {filename}"
    )


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
