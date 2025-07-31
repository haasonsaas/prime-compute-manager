"""Job queue management for batch processing."""

import asyncio
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from .manager import PrimeManager
from .models import Job, JobStatus, Pod


class JobQueue:
    """Manages a queue of compute jobs."""
    
    def __init__(self, manager: PrimeManager, max_concurrent_jobs: int = 5):
        """Initialize job queue.
        
        Args:
            manager: PrimeManager instance
            max_concurrent_jobs: Maximum concurrent jobs
        """
        self.manager = manager
        self.max_concurrent_jobs = max_concurrent_jobs
        self._jobs: Dict[str, Job] = {}
        self._job_queue: List[str] = []
        self._running_jobs: Dict[str, asyncio.Task] = {}
        
    def add_job(
        self,
        script_path: str,
        name: Optional[str] = None,
        args: Optional[Dict[str, Any]] = None,
        env_vars: Optional[Dict[str, str]] = None,
        gpu_type: str = "H100_80GB",
        gpu_count: int = 1,
        **kwargs
    ) -> Job:
        """Add a job to the queue.
        
        Args:
            script_path: Path to script to run
            name: Optional job name
            args: Script arguments
            env_vars: Environment variables
            gpu_type: GPU type required
            gpu_count: Number of GPUs required
            **kwargs: Additional job configuration
            
        Returns:
            Created job
        """
        if name is None:
            name = f"job-{uuid.uuid4().hex[:8]}"
        
        job = Job(
            id=f"job-{uuid.uuid4().hex}",
            name=name,
            status=JobStatus.PENDING,
            script_path=script_path,
            args=args or {},
            env_vars=env_vars or {},
            created_at=datetime.utcnow()
        )
        
        # Store job requirements
        job.metadata = {
            "gpu_type": gpu_type,
            "gpu_count": gpu_count,
            **kwargs
        }
        
        self._jobs[job.id] = job
        self._job_queue.append(job.id)
        
        return job
    
    async def _run_job(self, job: Job) -> None:
        """Run a single job.
        
        Args:
            job: Job to run
        """
        try:
            job.status = JobStatus.RUNNING
            job.started_at = datetime.utcnow()
            
            # Create pod for job
            pod = self.manager.create_pod(
                gpu_type=job.metadata["gpu_type"],
                gpu_count=job.metadata["gpu_count"],
                name=f"{job.name}-pod"
            )
            
            job.pod_id = pod.id
            
            # Wait for pod to be ready
            while True:
                pod_status = self.manager.get_pod_status(pod.id)
                if pod_status.status.value == "running":
                    break
                elif pod_status.status.value == "failed":
                    raise RuntimeError("Pod failed to start")
                
                await asyncio.sleep(5)
            
            # Mock job execution - in real implementation, 
            # would SSH to pod and run the script
            await asyncio.sleep(10)  # Simulate job runtime
            
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            job.output_path = f"/outputs/{job.name}/results.txt"
            
            # Terminate pod
            self.manager.terminate_pod(pod.id)
            
        except Exception as e:
            job.status = JobStatus.FAILED
            job.completed_at = datetime.utcnow()
            job.error_message = str(e)
            
            # Clean up pod if it exists
            if job.pod_id:
                try:
                    self.manager.terminate_pod(job.pod_id)
                except:
                    pass
    
    async def process_all(self) -> None:
        """Process all jobs in the queue."""
        while self._job_queue or self._running_jobs:
            # Start new jobs up to concurrent limit
            while (len(self._running_jobs) < self.max_concurrent_jobs and 
                   self._job_queue):
                job_id = self._job_queue.pop(0)
                job = self._jobs[job_id]
                
                task = asyncio.create_task(self._run_job(job))
                self._running_jobs[job_id] = task
            
            # Wait for at least one job to complete
            if self._running_jobs:
                done, pending = await asyncio.wait(
                    self._running_jobs.values(),
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                # Clean up completed jobs
                completed_job_ids = []
                for job_id, task in self._running_jobs.items():
                    if task in done:
                        completed_job_ids.append(job_id)
                
                for job_id in completed_job_ids:
                    del self._running_jobs[job_id]
    
    def get_job_status(self, job_id: str) -> Job:
        """Get status of a specific job.
        
        Args:
            job_id: Job identifier
            
        Returns:
            Job information
        """
        if job_id not in self._jobs:
            raise ValueError(f"Job {job_id} not found")
        
        return self._jobs[job_id]
    
    def list_jobs(self, status_filter: Optional[JobStatus] = None) -> List[Job]:
        """List all jobs.
        
        Args:
            status_filter: Optional status to filter by
            
        Returns:
            List of jobs
        """
        jobs = list(self._jobs.values())
        
        if status_filter:
            jobs = [j for j in jobs if j.status == status_filter]
        
        return sorted(jobs, key=lambda j: j.created_at, reverse=True)
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a job.
        
        Args:
            job_id: Job identifier
            
        Returns:
            True if successful
        """
        if job_id not in self._jobs:
            raise ValueError(f"Job {job_id} not found")
        
        job = self._jobs[job_id]
        
        if job.status == JobStatus.PENDING:
            # Remove from queue
            if job_id in self._job_queue:
                self._job_queue.remove(job_id)
            job.status = JobStatus.CANCELLED
            job.completed_at = datetime.utcnow()
            return True
        
        elif job.status == JobStatus.RUNNING:
            # Cancel running task
            if job_id in self._running_jobs:
                task = self._running_jobs[job_id]
                task.cancel()
                del self._running_jobs[job_id]
            
            job.status = JobStatus.CANCELLED
            job.completed_at = datetime.utcnow()
            
            # Terminate pod
            if job.pod_id:
                try:
                    self.manager.terminate_pod(job.pod_id)
                except:
                    pass
            
            return True
        
        return False