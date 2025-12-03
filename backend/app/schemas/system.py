"""
Chowkidaar NVR - System Monitoring Schemas
"""
from typing import Optional, List, Dict
from pydantic import BaseModel


class CPUStats(BaseModel):
    usage_percent: float
    cores: int
    frequency_mhz: float
    temperature: Optional[float] = None


class MemoryStats(BaseModel):
    total_gb: float
    used_gb: float
    available_gb: float
    usage_percent: float


class DiskStats(BaseModel):
    total_gb: float
    used_gb: float
    free_gb: float
    usage_percent: float
    mount_point: str


class GPUStats(BaseModel):
    id: int
    name: str
    memory_total_mb: float
    memory_used_mb: float
    memory_free_mb: float
    usage_percent: float
    temperature: Optional[float] = None


class NetworkStats(BaseModel):
    bytes_sent: int
    bytes_recv: int
    packets_sent: int
    packets_recv: int


class ProcessStats(BaseModel):
    pid: int
    name: str
    cpu_percent: float
    memory_percent: float


class InferenceStats(BaseModel):
    model_name: str
    inference_count: int
    average_inference_time_ms: float
    last_inference_time_ms: float
    fps: float


class SystemStats(BaseModel):
    cpu: CPUStats
    memory: MemoryStats
    disks: List[DiskStats]
    gpus: List[GPUStats]
    network: NetworkStats
    inference: Optional[InferenceStats] = None
    active_streams: int
    total_cameras: int
    timestamp: str


class SystemHealth(BaseModel):
    status: str  # healthy, warning, critical
    cpu_status: str
    memory_status: str
    gpu_status: str
    disk_status: str
    ollama_status: str
    database_status: str
    issues: List[str] = []
