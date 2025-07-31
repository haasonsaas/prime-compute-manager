"""Direct API client for PrimeIntellect API."""

import os
import time
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
            config_path = os.path.expanduser("~/.prime/config.json")
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
    
    def _make_request_with_retry(self, url: str, params: dict, max_retries: int = 3, base_delay: float = 1.0) -> dict:
        """Make HTTP request with exponential backoff retry on rate limits."""
        for attempt in range(max_retries + 1):
            try:
                response = self.session.get(url, params=params, timeout=30)
                response.raise_for_status()
                return response.json()
                
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429:  # Rate limited
                    if attempt < max_retries:
                        delay = base_delay * (2 ** attempt)  # Exponential backoff
                        time.sleep(delay)
                        continue
                    else:
                        raise RuntimeError("Rate limit exceeded after retries. Please wait before trying again.")
                elif e.response.status_code == 401:
                    raise RuntimeError("Unauthorized. Please run 'prime login' to authenticate.")
                else:
                    raise RuntimeError(f"API request failed: {e}")
            except requests.exceptions.Timeout:
                if attempt < max_retries:
                    delay = base_delay * (2 ** attempt)
                    time.sleep(delay)
                    continue
                else:
                    raise RuntimeError("API request timed out after retries.")
            except requests.exceptions.RequestException as e:
                raise RuntimeError(f"API request failed: {e}")
    
    def get_availability(
        self,
        regions: Optional[List[str]] = None,
        gpu_count: Optional[int] = None,
        gpu_type: Optional[str] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Get GPU availability from the API.
        
        Args:
            regions: List of regions to filter by
            gpu_count: Minimum GPU count
            gpu_type: Specific GPU type to filter
            
        Returns:
            Dictionary mapping GPU types to lists of availability data
        """
        params = {}
        
        if regions:
            params["regions"] = []
            for region in regions:
                params["regions"].extend(r.strip() for r in region.split(","))
        if gpu_count:
            params["gpu_count"] = str(gpu_count)
        if gpu_type:
            params["gpu_type"] = gpu_type
        
        try:
            # Get single GPU availability with retry logic
            single_gpus = self._make_request_with_retry(
                f"{self.base_url}/api/v1/availability",
                params=params
            )
            
            # Get cluster availability with retry logic
            clusters = self._make_request_with_retry(
                f"{self.base_url}/api/v1/availability/clusters",
                params=params
            )
            
            # Combine results - API returns dict with GPU types as keys
            combined = {}
            if isinstance(single_gpus, dict):
                for gpu_type_key, gpus in single_gpus.items():
                    if gpu_type_key is not None:
                        combined[gpu_type_key] = gpus
            if isinstance(clusters, dict):
                for gpu_type_key, gpus in clusters.items():
                    if gpu_type_key is not None:
                        if gpu_type_key in combined:
                            combined[gpu_type_key].extend(gpus)
                        else:
                            combined[gpu_type_key] = gpus

            return combined
            
        except Exception as e:
            # Re-raise RuntimeError from retry logic, wrap other exceptions
            if isinstance(e, RuntimeError):
                raise
            else:
                raise RuntimeError(f"Unexpected error during API call: {e}")
    
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
    
    def to_gpu_resources(self, api_data: Dict[str, List[Dict[str, Any]]]) -> List[GPUResource]:
        """Convert API response to GPUResource objects."""
        resources = []
        
        # API data is now a dict with GPU types as keys and lists of configs as values
        for gpu_type_str, gpu_configs in api_data.items():
            gpu_type = self.map_gpu_type(gpu_type_str)
            
            for item in gpu_configs:
                # Extract pricing using the actual structure from prime-cli
                prices = item.get("prices", {})
                if isinstance(prices, dict):
                    # Use community price if available, otherwise on_demand
                    price = prices.get("communityPrice", prices.get("onDemand", 0))
                else:
                    price = 0

                # Use stock status to determine availability
                stock_status = item.get("stockStatus", "").lower()
                if stock_status == "available":
                    available = item.get("gpuCount", 1)  # If available, use gpu count
                elif stock_status == "low":
                    available = max(1, item.get("gpuCount", 1) // 4)  # Low stock
                elif stock_status == "medium":
                    available = max(1, item.get("gpuCount", 1) // 2)  # Medium stock
                elif stock_status == "high":
                    available = item.get("gpuCount", 1)  # High availability
                else:
                    available = 0  # No stock

                total = item.get("gpuCount", available)

                resource = GPUResource(
                    gpu_type=gpu_type,
                    available_count=available,
                    total_count=total,
                    cost_per_hour=float(price) if price else 0.0,
                    provider=item.get("provider", "Unknown"),
                    region=item.get("country") or item.get("dataCenter") or "Unknown",
                    prime_id=item.get("cloudId", "")
                )

                resources.append(resource)
        
        return resources