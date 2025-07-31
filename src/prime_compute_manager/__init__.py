"""Prime Compute Manager - GPU resource management with PrimeIntellect integration."""

__version__ = "0.1.0"

from .manager import PrimeManager
from .models import Pod, GPUResource, JobStatus
from .queue import JobQueue
from .monitor import ResourceMonitor

__all__ = [
    "PrimeManager",
    "Pod",
    "GPUResource", 
    "JobStatus",
    "JobQueue",
    "ResourceMonitor",
]