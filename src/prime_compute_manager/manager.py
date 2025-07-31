"""Main PrimeManager class for GPU resource management."""

import subprocess
import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from .models import GPUResource, Pod, GPUType, PodStatus, Job, JobStatus


class PrimeManager:
    """Main manager for PrimeIntellect GPU resources."""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize the PrimeManager.
        
        Args:
            config_path: Optional path to configuration file
        """
        self.config_path = config_path
        self._pods: Dict[str, Pod] = {}
        self._jobs: Dict[str, Job] = {}
    
    def _run_prime_command(self, command: List[str]) -> Dict[str, Any]:
        """Run a prime-cli command and return parsed JSON result.
        
        Args:
            command: Command arguments to pass to prime-cli
            
        Returns:
            Parsed JSON response from prime-cli
            
        Raises:
            RuntimeError: If command fails
        """
        try:
            result = subprocess.run(
                ["prime"] + command,
                capture_output=True,
                text=True,
                check=True
            )
            
            # Try to parse JSON output
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError:
                # If not JSON, return stdout as text
                return {"output": result.stdout.strip()}
                
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Prime CLI command failed: {e.stderr}")
    
    def find_gpus(
        self, 
        gpu_type: Optional[str] = None,
        min_count: int = 1,
        max_cost_per_hour: Optional[float] = None,
        region: Optional[str] = None
    ) -> List[GPUResource]:
        """Find available GPU resources.
        
        Args:
            gpu_type: Specific GPU type to search for
            min_count: Minimum number of GPUs needed
            max_cost_per_hour: Maximum cost per hour per GPU
            region: Preferred region
            
        Returns:
            List of available GPU resources
        """
        # Build command
        cmd = ["availability", "list"]
        if gpu_type:
            cmd.extend(["--gpu-type", gpu_type])
        if region:
            cmd.extend(["--region", region])
        
        try:
            result = self._run_prime_command(cmd)
            
            # Parse the result and convert to GPUResource objects
            resources = []
            
            # Mock data for now - in real implementation, parse prime-cli output
            mock_resources = [
                {
                    "gpu_type": gpu_type or "H100_80GB",
                    "available_count": 4,
                    "total_count": 8,
                    "cost_per_hour": 3.20,
                    "provider": "AWS",
                    "region": region or "us-west-2",
                },
                {
                    "gpu_type": gpu_type or "H100_80GB", 
                    "available_count": 2,
                    "total_count": 4,
                    "cost_per_hour": 2.95,
                    "provider": "GCP",
                    "region": region or "us-central1",
                }
            ]
            
            for resource_data in mock_resources:
                available_count = int(resource_data["available_count"])
                cost_per_hour = float(resource_data["cost_per_hour"])
                if available_count >= min_count:
                    if max_cost_per_hour is None or cost_per_hour <= max_cost_per_hour:
                        resources.append(GPUResource(**resource_data))
            
            return resources
            
        except Exception as e:
            raise RuntimeError(f"Failed to find GPUs: {e}")
    
    def create_pod(
        self,
        gpu_type: str,
        gpu_count: int = 1,
        name: Optional[str] = None,
        region: Optional[str] = None,
        image: Optional[str] = None,
        **kwargs
    ) -> Pod:
        """Create a new compute pod.
        
        Args:
            gpu_type: Type of GPU to request
            gpu_count: Number of GPUs
            name: Optional pod name
            region: Preferred region
            image: Container image to use
            **kwargs: Additional pod configuration
            
        Returns:
            Created pod information
        """
        if name is None:
            name = f"pod-{uuid.uuid4().hex[:8]}"
        
        # Build command
        cmd = ["pods", "create"]
        cmd.extend(["--gpu-type", gpu_type])
        cmd.extend(["--gpu-count", str(gpu_count)])
        cmd.extend(["--name", name])
        
        if region:
            cmd.extend(["--region", region])
        if image:
            cmd.extend(["--image", image])
        
        try:
            result = self._run_prime_command(cmd)
            
            # Mock pod creation response
            pod_id = f"pod-{uuid.uuid4().hex}"
            
            pod = Pod(
                id=pod_id,
                name=name,
                status=PodStatus.CREATING,
                gpu_type=GPUType(gpu_type),
                gpu_count=gpu_count,
                cost_per_hour=3.20 * gpu_count,  # Mock cost
                created_at=datetime.utcnow(),
                provider="AWS",  # Mock provider
                region=region or "us-west-2",
                metadata=kwargs
            )
            
            self._pods[pod_id] = pod
            return pod
            
        except Exception as e:
            raise RuntimeError(f"Failed to create pod: {e}")
    
    def get_pod_status(self, pod_id: str) -> Pod:
        """Get current status of a pod.
        
        Args:
            pod_id: Pod identifier
            
        Returns:
            Updated pod information
        """
        if pod_id not in self._pods:
            raise ValueError(f"Pod {pod_id} not found")
        
        try:
            # In real implementation, query prime-cli for actual status
            pod = self._pods[pod_id]
            
            # Mock status update
            if pod.status == PodStatus.CREATING:
                pod.status = PodStatus.RUNNING
                pod.started_at = datetime.utcnow()
                pod.ssh_connection = f"ssh user@{pod_id}.prime.example.com"
            
            return pod
            
        except Exception as e:
            raise RuntimeError(f"Failed to get pod status: {e}")
    
    def list_pods(self, active_only: bool = True) -> List[Pod]:
        """List all pods.
        
        Args:
            active_only: Only return active pods
            
        Returns:
            List of pods
        """
        try:
            cmd = ["pods", "list"]
            result = self._run_prime_command(cmd)
            
            pods = list(self._pods.values())
            
            if active_only:
                pods = [p for p in pods if p.status in [PodStatus.CREATING, PodStatus.RUNNING]]
            
            return pods
            
        except Exception as e:
            raise RuntimeError(f"Failed to list pods: {e}")
    
    def terminate_pod(self, pod_id: str) -> bool:
        """Terminate a pod.
        
        Args:
            pod_id: Pod identifier
            
        Returns:
            True if successful
        """
        if pod_id not in self._pods:
            raise ValueError(f"Pod {pod_id} not found")
        
        try:
            cmd = ["pods", "terminate", pod_id]
            self._run_prime_command(cmd)
            
            # Update local state
            pod = self._pods[pod_id]
            pod.status = PodStatus.STOPPED
            pod.stopped_at = datetime.utcnow()
            
            return True
            
        except Exception as e:
            raise RuntimeError(f"Failed to terminate pod: {e}")
    
    def ssh_to_pod(self, pod_id: str) -> str:
        """Get SSH connection string for a pod.
        
        Args:
            pod_id: Pod identifier
            
        Returns:
            SSH connection command
        """
        pod = self.get_pod_status(pod_id)
        
        if pod.status != PodStatus.RUNNING:
            raise RuntimeError(f"Pod {pod_id} is not running")
        
        if not pod.ssh_connection:
            raise RuntimeError(f"SSH connection not available for pod {pod_id}")
        
        return pod.ssh_connection