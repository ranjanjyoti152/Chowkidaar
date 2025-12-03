"""
Chowkidaar NVR - System Monitoring Service
"""
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
import psutil
from loguru import logger

from app.core.config import settings
from app.schemas.system import (
    CPUStats, MemoryStats, DiskStats, GPUStats,
    NetworkStats, SystemStats, SystemHealth, InferenceStats
)


class SystemMonitor:
    """System resource monitoring service"""
    
    def __init__(self):
        self._gpu_available = False
        self._initialize_gpu()
    
    def _initialize_gpu(self):
        """Check if GPU monitoring is available"""
        try:
            import GPUtil
            gpus = GPUtil.getGPUs()
            self._gpu_available = len(gpus) > 0
            if self._gpu_available:
                logger.info(f"GPU monitoring enabled: {len(gpus)} GPU(s) found")
        except Exception as e:
            logger.warning(f"GPU monitoring not available: {e}")
            self._gpu_available = False
    
    async def get_cpu_stats(self) -> CPUStats:
        """Get CPU statistics"""
        loop = asyncio.get_event_loop()
        
        # Get CPU usage (blocking call)
        usage = await loop.run_in_executor(
            None,
            lambda: psutil.cpu_percent(interval=0.1)
        )
        
        freq = psutil.cpu_freq()
        
        # Try to get temperature (Linux only)
        temperature = None
        try:
            temps = psutil.sensors_temperatures()
            if temps:
                # Try common sensor names
                for name in ["coretemp", "cpu_thermal", "k10temp"]:
                    if name in temps:
                        temperature = temps[name][0].current
                        break
        except:
            pass
        
        return CPUStats(
            usage_percent=usage,
            cores=psutil.cpu_count(logical=True),
            frequency_mhz=freq.current if freq else 0,
            temperature=temperature
        )
    
    async def get_memory_stats(self) -> MemoryStats:
        """Get memory statistics"""
        mem = psutil.virtual_memory()
        
        return MemoryStats(
            total_gb=round(mem.total / (1024**3), 2),
            used_gb=round(mem.used / (1024**3), 2),
            available_gb=round(mem.available / (1024**3), 2),
            usage_percent=mem.percent
        )
    
    async def get_disk_stats(self) -> List[DiskStats]:
        """Get disk statistics"""
        disks = []
        
        for partition in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                disks.append(DiskStats(
                    total_gb=round(usage.total / (1024**3), 2),
                    used_gb=round(usage.used / (1024**3), 2),
                    free_gb=round(usage.free / (1024**3), 2),
                    usage_percent=usage.percent,
                    mount_point=partition.mountpoint
                ))
            except PermissionError:
                continue
        
        return disks
    
    async def get_gpu_stats(self) -> List[GPUStats]:
        """Get GPU statistics"""
        if not self._gpu_available:
            return []
        
        try:
            import GPUtil
            gpus = GPUtil.getGPUs()
            
            return [
                GPUStats(
                    id=gpu.id,
                    name=gpu.name,
                    memory_total_mb=gpu.memoryTotal,
                    memory_used_mb=gpu.memoryUsed,
                    memory_free_mb=gpu.memoryFree,
                    usage_percent=gpu.load * 100,
                    temperature=gpu.temperature
                )
                for gpu in gpus
            ]
        except Exception as e:
            logger.error(f"GPU stats error: {e}")
            return []
    
    async def get_network_stats(self) -> NetworkStats:
        """Get network statistics"""
        net = psutil.net_io_counters()
        
        return NetworkStats(
            bytes_sent=net.bytes_sent,
            bytes_recv=net.bytes_recv,
            packets_sent=net.packets_sent,
            packets_recv=net.packets_recv
        )
    
    async def get_system_stats(
        self,
        active_streams: int = 0,
        total_cameras: int = 0,
        inference_stats: Optional[InferenceStats] = None
    ) -> SystemStats:
        """Get complete system statistics"""
        
        # Gather stats concurrently
        cpu, memory, disks, gpus, network = await asyncio.gather(
            self.get_cpu_stats(),
            self.get_memory_stats(),
            self.get_disk_stats(),
            self.get_gpu_stats(),
            self.get_network_stats()
        )
        
        return SystemStats(
            cpu=cpu,
            memory=memory,
            disks=disks,
            gpus=gpus,
            network=network,
            inference=inference_stats,
            active_streams=active_streams,
            total_cameras=total_cameras,
            timestamp=datetime.utcnow().isoformat()
        )
    
    async def check_health(
        self,
        db_healthy: bool = True,
        ollama_healthy: bool = True
    ) -> SystemHealth:
        """Check overall system health"""
        issues = []
        
        cpu = await self.get_cpu_stats()
        memory = await self.get_memory_stats()
        gpus = await self.get_gpu_stats()
        disks = await self.get_disk_stats()
        
        # CPU status
        if cpu.usage_percent > 90:
            cpu_status = "critical"
            issues.append("CPU usage critically high")
        elif cpu.usage_percent > 75:
            cpu_status = "warning"
            issues.append("CPU usage high")
        else:
            cpu_status = "healthy"
        
        # Memory status
        if memory.usage_percent > 90:
            memory_status = "critical"
            issues.append("Memory usage critically high")
        elif memory.usage_percent > 80:
            memory_status = "warning"
            issues.append("Memory usage high")
        else:
            memory_status = "healthy"
        
        # GPU status
        gpu_status = "healthy"
        if gpus:
            max_gpu_usage = max(g.usage_percent for g in gpus)
            if max_gpu_usage > 95:
                gpu_status = "critical"
                issues.append("GPU usage critically high")
            elif max_gpu_usage > 85:
                gpu_status = "warning"
                issues.append("GPU usage high")
        else:
            gpu_status = "unavailable"
        
        # Disk status
        disk_status = "healthy"
        for disk in disks:
            if disk.usage_percent > 95:
                disk_status = "critical"
                issues.append(f"Disk {disk.mount_point} almost full")
            elif disk.usage_percent > 85:
                if disk_status != "critical":
                    disk_status = "warning"
                issues.append(f"Disk {disk.mount_point} usage high")
        
        # Database status
        database_status = "healthy" if db_healthy else "error"
        if not db_healthy:
            issues.append("Database connection error")
        
        # Ollama status
        ollama_status = "healthy" if ollama_healthy else "error"
        if not ollama_healthy:
            issues.append("Ollama VLM not available")
        
        # Overall status
        if "critical" in [cpu_status, memory_status, gpu_status, disk_status]:
            overall_status = "critical"
        elif "warning" in [cpu_status, memory_status, gpu_status, disk_status]:
            overall_status = "warning"
        elif "error" in [database_status, ollama_status]:
            overall_status = "warning"
        else:
            overall_status = "healthy"
        
        return SystemHealth(
            status=overall_status,
            cpu_status=cpu_status,
            memory_status=memory_status,
            gpu_status=gpu_status,
            disk_status=disk_status,
            ollama_status=ollama_status,
            database_status=database_status,
            issues=issues
        )


# Global system monitor instance
system_monitor = SystemMonitor()


def get_system_monitor() -> SystemMonitor:
    """Get the system monitor instance"""
    return system_monitor
