"""Direct API client for PrimeIntellect API."""

import os
from typing import Dict, List, Optional, Any
import requests
from .models import GPUResource, GPUType

class PrimeAPIClient:
    """Direct API client for PrimeIntellect, based on prime-cli's implementation."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the API client.
        
        Args:
            api_key: API key for authentication. If not provided, will look for PRIME_API_KEY env var.
        """
        self.api_key = api_key or os.environ.get("PRIME_API_KEY")
        if not self.api_key:
            # Try to read from prime-cli config
            config_path = os.path.expanduser("~/.config/prime/config.json")
            if os.path.exists(config_path):
                import json
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    self.api_key = config.get("api_key")
        
        if not self.api_key:
            raise ValueError("No API key found. Please set PRIME_API_KEY or run 'prime login'")
        
        self.base_url = "https://api.primeintellect.ai"
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        })
    
    def get_availability(
        self,
        regions: Optional[List[str]] = None,
        gpu_count: Optional[int] = None,
        gpu_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get GPU availability from the API.
        
        Args:
            regions: List of regions to filter by
            gpu_count: Minimum GPU count
            gpu_type: Specific GPU type to filter
            
        Returns:
            List of availability data
        """
        params = {}
        
        if regions:
            params["regions"] = ",".join(regions)
        if gpu_count:
            params["gpu_count"] = str(gpu_count)
        if gpu_type:
            params["gpu_type"] = gpu_type
        
        try:
            # Get single GPU availability
            response = self.session.get(
                f"{self.base_url}/api/v1/availability",
                params=params
            )
            response.raise_for_status()
            single_gpus = response.json()
            
            # Get cluster availability
            cluster_response = self.session.get(
                f"{self.base_url}/api/v1/availability/clusters",
                params=params
            )
            cluster_response.raise_for_status()
            clusters = cluster_response.json()
            
            # Combine results
            all_resources = []
            if isinstance(single_gpus, list):
                all_resources.extend(single_gpus)
            if isinstance(clusters, list):
                all_resources.extend(clusters)
                
            return all_resources
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                raise RuntimeError("Unauthorized. Please run 'prime login' to authenticate.")
            elif e.response.status_code == 429:
                raise RuntimeError("Rate limit exceeded. Please wait before retrying.")
            else:
                raise RuntimeError(f"API request failed: {e}")
    
    def map_gpu_type(self, gpu_type_str: str) -> GPUType:
        """Map API GPU type string to our enum."""
        gpu_upper = gpu_type_str.upper()
        
        # Try exact match first
        for gpu_type in GPUType:
            if gpu_type.value == gpu_upper:
                return gpu_type
        
        # Try without underscores
        for gpu_type in GPUType:
            if gpu_type.value.replace("_", "") == gpu_upper.replace("_", ""):
                return gpu_type
        
        # Try partial matches
        if "H100" in gpu_upper:
            if "80" in gpu_upper:
                return GPUType.H100_80GB
            elif "40" in gpu_upper:
                return GPUType.H100_40GB
            return GPUType.H100_80GB
        
        elif "A100" in gpu_upper:
            if "80" in gpu_upper:
                return GPUType.A100_80GB
            elif "40" in gpu_upper:
                return GPUType.A100_40GB
            return GPUType.A100_80GB
        
        elif "V100" in gpu_upper:
            if "32" in gpu_upper:
                return GPUType.V100_32GB
            elif "16" in gpu_upper:
                return GPUType.V100_16GB
            return GPUType.V100_16GB
        
        elif "A6000" in gpu_upper or "RTXA6000" in gpu_upper:
            return GPUType.RTX_A6000
        
        elif "A5000" in gpu_upper or "RTXA5000" in gpu_upper:
            return GPUType.RTX_A5000
        
        elif "A4000" in gpu_upper or "RTXA4000" in gpu_upper:
            return GPUType.RTX_A4000
        
        elif "L40S" in gpu_upper:
            return GPUType.L40S
        elif "L40" in gpu_upper:
            return GPUType.L40
        elif "L4" in gpu_upper:
            return GPUType.L4
        
        elif "4090" in gpu_upper:
            return GPUType.RTX_4090
        elif "4080" in gpu_upper:
            return GPUType.RTX_4080
        elif "3090" in gpu_upper:
            return GPUType.RTX_3090
        
        elif "T4" in gpu_upper:
            return GPUType.T4
        
        elif "CPU" in gpu_upper:
            return GPUType.CPU
        
        return GPUType.UNKNOWN
    
    def to_gpu_resources(self, api_data: List[Dict[str, Any]]) -> List[GPUResource]:
        """Convert API response to GPUResource objects."""
        resources = []
        
        for item in api_data:
            # Extract pricing
            prices = item.get("prices", {})
            if isinstance(prices, dict):
                # Use community price if available, otherwise on_demand
                price = prices.get("community", prices.get("on_demand", 0))
            else:
                price = 0
            
            # Extract GPU info
            gpu_type_str = item.get("gpu_type", "UNKNOWN")
            gpu_type = self.map_gpu_type(gpu_type_str)
            
            # Get availability status
            availability = item.get("availability", {})
            if isinstance(availability, dict):
                available = availability.get("available", 0)
                total = availability.get("total", 0)
            else:
                # Fallback for different response format
                available = item.get("available_gpus", 0)
                total = item.get("total_gpus", available)
            
            resource = GPUResource(
                gpu_type=gpu_type,
                available_count=available,
                total_count=total,
                cost_per_hour=float(price) if price else 0.0,
                provider=item.get("provider", "Unknown"),
                region=item.get("country", item.get("location", "Unknown")),
                prime_id=item.get("id", "")
            )
            
            resources.append(resource)
        
        return resources