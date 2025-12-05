"""
Chowkidaar NVR - Services Module
"""
from app.services.yolo_detector import YOLODetector, get_detector
from app.services.stream_handler import (
    RTSPStreamHandler, StreamManager, StreamState, StreamInfo, get_stream_manager
)
from app.services.vlm_service import (
    UnifiedVLMService, 
    get_unified_vlm_service, 
    get_vlm_service,  # Backwards compat - now uses UnifiedVLMService
    OllamaProvider,
    OpenAIProvider,
    GeminiProvider
)
from app.services.event_processor import EventProcessor, get_event_processor
from app.services.system_monitor import SystemMonitor, get_system_monitor

__all__ = [
    "YOLODetector",
    "get_detector",
    "RTSPStreamHandler",
    "StreamManager",
    "StreamState",
    "StreamInfo",
    "get_stream_manager",
    "UnifiedVLMService",
    "get_unified_vlm_service",
    "get_vlm_service",
    "OllamaProvider",
    "OpenAIProvider",
    "GeminiProvider",
    "EventProcessor",
    "get_event_processor",
    "SystemMonitor",
    "get_system_monitor"
]
