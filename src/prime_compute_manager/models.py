"""Data models for Prime Compute Manager."""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    """Status of a compute job."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PodStatus(str, Enum):
    """Status of a compute pod."""
    CREATING = "creating"
    RUNNING = "running"
    STOPPING = "stopping" 
    STOPPED = "stopped"
    FAILED = "failed"


class GPUType(str, Enum):
    """Supported GPU types."""
    H100_80GB = "H100_80GB"
    A100_80GB = "A100_80GB"
    A100_40GB = "A100_40GB"
    V100_32GB = "V100_32GB"
    RTX_4090 = "RTX_4090"


class GPUResource(BaseModel):
    """GPU resource information."""
    gpu_type: GPUType
    available_count: int
    total_count: int
    cost_per_hour: float
    provider: str
    region: str
    availability_zone: Optional[str] = None
    prime_id: Optional[str] = None  # Store the original prime-cli configuration ID
    
    @property
    def utilization(self) -> float:
        """Calculate GPU utilization percentage."""
        if self.total_count == 0:
            return 0.0
        return (self.total_count - self.available_count) / self.total_count * 100


class Pod(BaseModel):
    """Compute pod information."""
    id: str
    name: str
    status: PodStatus
    gpu_type: GPUType
    gpu_count: int
    cost_per_hour: float
    created_at: datetime
    started_at: Optional[datetime] = None
    stopped_at: Optional[datetime] = None
    ssh_connection: Optional[str] = None
    provider: str
    region: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @property
    def runtime_hours(self) -> float:
        """Calculate pod runtime in hours."""
        if not self.started_at:
            return 0.0
        
        end_time = self.stopped_at or datetime.utcnow()
        runtime = end_time - self.started_at
        return runtime.total_seconds() / 3600
    
    @property
    def total_cost(self) -> float:
        """Calculate total cost of pod."""
        return self.runtime_hours * self.cost_per_hour


class Job(BaseModel):
    """Compute job information."""
    id: str
    name: str
    status: JobStatus
    pod_id: Optional[str] = None
    script_path: str
    args: Dict[str, Any] = Field(default_factory=dict)
    env_vars: Dict[str, str] = Field(default_factory=dict)
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    output_path: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @property
    def runtime_seconds(self) -> float:
        """Calculate job runtime in seconds."""
        if not self.started_at:
            return 0.0
        
        end_time = self.completed_at or datetime.utcnow()
        runtime = end_time - self.started_at
        return runtime.total_seconds()


class TeamUsage(BaseModel):
    """Team resource usage information."""
    team_name: str
    active_pods: int
    total_gpus_used: int
    current_cost_per_hour: float
    total_cost_today: float
    total_cost_month: float
    pod_breakdown: List[Pod] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    
class Alert(BaseModel):
    """Resource usage alert."""
    id: str
    name: str
    condition: str
    action: str
    recipient: str
    is_active: bool = True
    last_triggered: Optional[datetime] = None