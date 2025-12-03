"""
Chowkidaar NVR - RTSP Stream Handler Service
"""
import asyncio
from typing import Dict, Any, Optional, Callable, AsyncGenerator
from datetime import datetime
import cv2
import numpy as np
from loguru import logger
import threading
from queue import Queue, Empty
from dataclasses import dataclass
from enum import Enum

from app.core.config import settings
from app.models.camera import CameraStatus


class StreamState(Enum):
    IDLE = "idle"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"
    STOPPED = "stopped"


@dataclass
class StreamInfo:
    camera_id: int
    url: str
    state: StreamState
    fps: int
    resolution: Optional[tuple] = None
    last_frame_time: Optional[datetime] = None
    error_message: Optional[str] = None
    frame_count: int = 0


class RTSPStreamHandler:
    """Handles RTSP camera stream processing"""
    
    def __init__(self, camera_id: int, stream_url: str, fps: int = 15):
        self.camera_id = camera_id
        self.stream_url = stream_url
        self.target_fps = fps
        self.buffer_size = settings.stream_buffer_size
        
        self._cap: Optional[cv2.VideoCapture] = None
        self._frame_queue: Queue = Queue(maxsize=self.buffer_size)
        self._state = StreamState.IDLE
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._callbacks: list = []
        
        self.info = StreamInfo(
            camera_id=camera_id,
            url=stream_url,
            state=StreamState.IDLE,
            fps=fps
        )
    
    def add_callback(self, callback: Callable[[np.ndarray, int], None]):
        """Add a callback for new frames"""
        self._callbacks.append(callback)
    
    def _capture_loop(self):
        """Internal capture loop running in a separate thread"""
        reconnect_delay = settings.stream_reconnect_delay
        frame_interval = 1.0 / self.target_fps
        
        while self._running:
            try:
                # Connect to stream
                self._state = StreamState.CONNECTING
                self.info.state = StreamState.CONNECTING
                
                logger.info(f"Camera {self.camera_id}: Connecting to {self.stream_url}")
                
                self._cap = cv2.VideoCapture(self.stream_url)
                self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                
                if not self._cap.isOpened():
                    raise ConnectionError("Failed to open stream")
                
                # Get stream info
                width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                self.info.resolution = (width, height)
                
                self._state = StreamState.CONNECTED
                self.info.state = StreamState.CONNECTED
                self.info.error_message = None
                
                logger.info(f"Camera {self.camera_id}: Connected ({width}x{height})")
                
                last_frame_time = datetime.utcnow()
                
                while self._running and self._cap.isOpened():
                    ret, frame = self._cap.read()
                    
                    if not ret:
                        logger.warning(f"Camera {self.camera_id}: Failed to read frame")
                        break
                    
                    # Rate limiting
                    now = datetime.utcnow()
                    elapsed = (now - last_frame_time).total_seconds()
                    if elapsed < frame_interval:
                        continue
                    
                    last_frame_time = now
                    self.info.last_frame_time = now
                    self.info.frame_count += 1
                    
                    # Add to queue (non-blocking)
                    try:
                        if self._frame_queue.full():
                            self._frame_queue.get_nowait()  # Remove oldest
                        self._frame_queue.put_nowait(frame)
                    except:
                        pass
                    
                    # Notify callbacks
                    for callback in self._callbacks:
                        try:
                            callback(frame, self.camera_id)
                        except Exception as e:
                            logger.error(f"Callback error: {e}")
                
            except Exception as e:
                logger.error(f"Camera {self.camera_id}: Stream error - {e}")
                self._state = StreamState.ERROR
                self.info.state = StreamState.ERROR
                self.info.error_message = str(e)
            
            finally:
                if self._cap:
                    self._cap.release()
                    self._cap = None
            
            # Reconnect if still running
            if self._running:
                self._state = StreamState.RECONNECTING
                self.info.state = StreamState.RECONNECTING
                logger.info(f"Camera {self.camera_id}: Reconnecting in {reconnect_delay}s")
                
                for _ in range(reconnect_delay):
                    if not self._running:
                        break
                    threading.Event().wait(1)
        
        self._state = StreamState.STOPPED
        self.info.state = StreamState.STOPPED
        logger.info(f"Camera {self.camera_id}: Stream stopped")
    
    async def start(self) -> bool:
        """Start the stream capture"""
        if self._running:
            return True
        
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        
        # Wait for initial connection
        for _ in range(50):  # 5 second timeout
            if self._state == StreamState.CONNECTED:
                return True
            if self._state == StreamState.ERROR:
                return False
            await asyncio.sleep(0.1)
        
        return self._state == StreamState.CONNECTED
    
    async def stop(self):
        """Stop the stream capture"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        
        # Clear queue
        while not self._frame_queue.empty():
            try:
                self._frame_queue.get_nowait()
            except Empty:
                break
    
    def get_frame(self) -> Optional[np.ndarray]:
        """Get the latest frame (non-blocking)"""
        try:
            return self._frame_queue.get_nowait()
        except Empty:
            return None
    
    async def get_frame_async(self, timeout: float = 1.0) -> Optional[np.ndarray]:
        """Get a frame asynchronously"""
        loop = asyncio.get_event_loop()
        try:
            return await loop.run_in_executor(
                None,
                lambda: self._frame_queue.get(timeout=timeout)
            )
        except Empty:
            return None
    
    async def frame_generator(self) -> AsyncGenerator[np.ndarray, None]:
        """Generate frames asynchronously"""
        while self._running:
            frame = await self.get_frame_async()
            if frame is not None:
                yield frame
            else:
                await asyncio.sleep(0.01)
    
    def get_status(self) -> CameraStatus:
        """Get camera status based on stream state"""
        mapping = {
            StreamState.IDLE: CameraStatus.OFFLINE,
            StreamState.CONNECTING: CameraStatus.CONNECTING,
            StreamState.CONNECTED: CameraStatus.ONLINE,
            StreamState.RECONNECTING: CameraStatus.CONNECTING,
            StreamState.ERROR: CameraStatus.ERROR,
            StreamState.STOPPED: CameraStatus.DISABLED
        }
        return mapping.get(self._state, CameraStatus.OFFLINE)
    
    def is_connected(self) -> bool:
        return self._state == StreamState.CONNECTED


class StreamManager:
    """Manages multiple camera streams"""
    
    def __init__(self):
        self._streams: Dict[int, RTSPStreamHandler] = {}
        self._lock = asyncio.Lock()
    
    async def add_stream(
        self,
        camera_id: int,
        stream_url: str,
        fps: int = 15
    ) -> RTSPStreamHandler:
        """Add and start a new stream"""
        async with self._lock:
            # Stop existing stream if any
            if camera_id in self._streams:
                await self._streams[camera_id].stop()
            
            # Create new handler
            handler = RTSPStreamHandler(camera_id, stream_url, fps)
            self._streams[camera_id] = handler
            
            # Start stream
            await handler.start()
            
            return handler
    
    async def remove_stream(self, camera_id: int):
        """Stop and remove a stream"""
        async with self._lock:
            if camera_id in self._streams:
                await self._streams[camera_id].stop()
                del self._streams[camera_id]
    
    def get_stream(self, camera_id: int) -> Optional[RTSPStreamHandler]:
        """Get a stream handler by camera ID"""
        return self._streams.get(camera_id)
    
    def get_all_streams(self) -> Dict[int, RTSPStreamHandler]:
        """Get all stream handlers"""
        return self._streams.copy()
    
    def get_active_count(self) -> int:
        """Get count of active streams"""
        return sum(1 for s in self._streams.values() if s.is_connected())
    
    async def stop_all(self):
        """Stop all streams"""
        async with self._lock:
            for handler in self._streams.values():
                await handler.stop()
            self._streams.clear()


# Global stream manager instance
stream_manager = StreamManager()


def get_stream_manager() -> StreamManager:
    """Get the stream manager instance"""
    return stream_manager
