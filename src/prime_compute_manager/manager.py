"""Main PrimeManager class for GPU resource management."""

import subprocess
import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from .models import GPUResource, Pod, GPUType, PodStatus, Job, JobStatus
from .parser import parse_availability_table, parse_pods_table, parse_gpu_types_table


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
    
    def _parse_pod_status(self, status_str: str) -> PodStatus:
        """Safely parse pod status string to PodStatus enum."""
        try:
            return PodStatus(status_str.lower())  # type: ignore
        except ValueError:
            # Default to RUNNING if status is not recognized
            return PodStatus.RUNNING
    
    def _parse_gpu_type(self, gpu_type_str: str) -> GPUType:
        """Safely parse GPU type string to GPUType enum."""
        # Extract the main GPU type (first part before any additional info)
        gpu_type_main = gpu_type_str.split()[0].upper()
        
        # Handle special cases
        if "CPU" in gpu_type_main:
            return GPUType.CPU
        
        # Try to match known GPU types
        for gpu_type in GPUType:
            if gpu_type.value == gpu_type_main:
                return gpu_type
            # Also try without underscores (e.g., RTX_4090 vs RTX4090)
            if gpu_type.value.replace("_", "") == gpu_type_main.replace("_", ""):
                return gpu_type
        
        # If no match found, return UNKNOWN
        return GPUType.UNKNOWN
    
    def _run_prime_command(self, command: List[str]) -> str:
        """Run a prime-cli command and return raw text output.
        
        Args:
            command: Command arguments to pass to prime-cli
            
        Returns:
            Raw text output from prime-cli
            
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
            
            return result.stdout
                
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Prime CLI command failed: {e.stderr}")
    
    def find_gpus(
        self, 
        gpu_type: Optional[str] = None,
        min_count: int = 1,
        max_cost_per_hour: Optional[float] = None,
        regions: Optional[str] = None,
        provider: Optional[str] = None
    ) -> List[GPUResource]:
        """Find available GPU resources.
        
        Args:
            gpu_type: Specific GPU type to search for
            min_count: Minimum number of GPUs needed
            max_cost_per_hour: Maximum cost per hour per GPU (filtered locally)
            regions: Preferred regions filter (e.g., 'united_states')
            provider: Provider filter (e.g., 'aws', 'azure', 'google')
            
        Returns:
            List of available GPU resources
        """
        # Build command
        cmd = ["availability", "list"]
        # Note: We filter gpu_type client-side to avoid API errors with unrecognized types
        if min_count > 1:
            cmd.extend(["--gpu-count", str(min_count)])
        if regions:
            cmd.extend(["--regions", regions])
        if provider:
            cmd.extend(["--provider", provider])
        
        try:
            output = self._run_prime_command(cmd)
            
            # Parse the table output
            parsed_resources = parse_availability_table(output)
            
            # Convert to GPUResource objects
            resources = []
            for resource_data in parsed_resources:
                # Parse GPU type first
                parsed_gpu_type = self._parse_gpu_type(resource_data["gpu_type"])
                
                # Apply filters including GPU type filter
                if gpu_type and parsed_gpu_type.value != gpu_type:
                    continue  # Skip if doesn't match requested GPU type
                    
                if resource_data["available_count"] >= min_count:
                    if max_cost_per_hour is None or resource_data["cost_per_hour"] <= max_cost_per_hour:
                        # Convert to our GPUResource model
                        gpu_resource = GPUResource(
                            gpu_type=parsed_gpu_type,
                            available_count=resource_data["available_count"],
                            total_count=resource_data["total_count"], 
                            cost_per_hour=resource_data["cost_per_hour"],
                            provider=resource_data["provider"],
                            region=resource_data["location"]
                        )
                        # Store the original ID for pod creation
                        gpu_resource.prime_id = resource_data["id"]
                        resources.append(gpu_resource)
            
            return resources
            
        except Exception as e:
            raise RuntimeError(f"Failed to find GPUs: {e}")
    
    def create_pod_from_config(
        self,
        prime_id: str,
        name: Optional[str] = None,
        **kwargs
    ) -> Pod:
        """Create a new compute pod using a prime-cli configuration ID.
        
        Args:
            prime_id: Configuration ID from prime availability list
            name: Optional pod name
            **kwargs: Additional pod configuration (stored as metadata)
            
        Returns:
            Created pod information
        """
        if name is None:
            name = f"pod-{uuid.uuid4().hex[:8]}"
        
        # Build command using --id parameter
        cmd = ["pods", "create", "--id", prime_id]
        if name:
            cmd.extend(["--name", name])
        
        try:
            # Note: This would be interactive in real usage
            # For now, we'll simulate the creation
            output = self._run_prime_command(cmd)
            
            # Parse the output to extract pod information
            # In real implementation, prime-cli would return pod details
            pod_id = f"pod-{uuid.uuid4().hex}"
            
            # Create pod object (this would normally be parsed from output)
            pod = Pod(
                id=pod_id,
                name=name,
                status=PodStatus.CREATING,
                gpu_type=GPUType.H100_80GB,  # Would be parsed from config
                gpu_count=1,  # Would be parsed from config
                cost_per_hour=3.20,  # Would be parsed from config
                created_at=datetime.utcnow(),
                provider="AWS",  # Would be parsed from config
                region="us-west-2",  # Would be parsed from config
                metadata={"prime_id": prime_id, **kwargs}
            )
            
            self._pods[pod_id] = pod
            return pod
            
        except Exception as e:
            raise RuntimeError(f"Failed to create pod: {e}")
    
    def create_pod(
        self,
        gpu_type: str,
        gpu_count: int = 1,
        name: Optional[str] = None,
        max_cost_per_hour: Optional[float] = None,
        **kwargs
    ) -> Pod:
        """Create a pod by finding a suitable configuration first.
        
        Args:
            gpu_type: Type of GPU to request
            gpu_count: Number of GPUs  
            name: Optional pod name
            max_cost_per_hour: Maximum acceptable cost per hour
            **kwargs: Additional pod configuration
            
        Returns:
            Created pod information
        """
        # First, find available resources
        resources = self.find_gpus(
            gpu_type=gpu_type,
            min_count=gpu_count,
            max_cost_per_hour=max_cost_per_hour
        )
        
        if not resources:
            raise RuntimeError(f"No available {gpu_type} resources found with {gpu_count} GPUs")
        
        # Use the first (cheapest) available resource
        selected_resource = resources[0]
        
        if not selected_resource.prime_id:
            raise RuntimeError("Selected resource missing prime_id for pod creation")
        
        # Create pod using the configuration ID
        return self.create_pod_from_config(
            prime_id=selected_resource.prime_id,
            name=name,
            **kwargs
        )
    
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
        """List all pods from prime-cli.
        
        Args:
            active_only: Only return active pods (ignored for now, prime-cli returns all active pods)
            
        Returns:
            List of pods
        """
        try:
            cmd = ["pods", "list"]
            output = self._run_prime_command(cmd)
            
            # Parse the table output
            parsed_pods = parse_pods_table(output)
            
            # Convert to Pod objects and merge with local cache
            pods = []
            for pod_data in parsed_pods:
                # Check if we have this pod in our local cache
                pod_id = pod_data["id"]
                if pod_id in self._pods:
                    # Update from cache
                    cached_pod = self._pods[pod_id]
                    cached_pod.status = self._parse_pod_status(pod_data["status"])
                    pods.append(cached_pod)
                else:
                    # Create new pod object
                    pod = Pod(
                        id=pod_id,
                        name=pod_data["name"],
                        status=PodStatus.RUNNING,  # Default to RUNNING, can parse later
                        gpu_type=GPUType.H100_80GB,  # Parse from gpu_info
                        gpu_count=1,  # Parse from gpu_info
                        cost_per_hour=0.0,  # Not available in list output
                        created_at=datetime.utcnow(),  # Parse from created field
                        provider="Unknown",
                        region="Unknown"
                    )
                    pods.append(pod)
            
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