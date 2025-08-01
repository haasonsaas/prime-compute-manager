"""Main PrimeManager class for GPU resource management."""

import subprocess
import json
import uuid
import sys
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
from .models import GPUResource, Pod, GPUType, PodStatus, Job, JobStatus
from .parser import parse_availability_table, parse_pods_table, parse_gpu_types_table

try:
    from .api_client import PrimeAPIClient

    HAS_API_CLIENT = True
except ImportError:
    HAS_API_CLIENT = False


class PrimeManager:
    """Main manager for PrimeIntellect GPU resources."""

    def __init__(self, config_path: Optional[str] = None, use_api: bool = True):
        """Initialize the PrimeManager.

        Args:
            config_path: Optional path to configuration file
            use_api: Whether to use the API client directly (requires API key)
        """
        self.config_path = config_path
        self._pods: Dict[str, Pod] = {}
        self._jobs: Dict[str, Job] = {}
        self.use_api = use_api and HAS_API_CLIENT
        self.api_client = None

        if self.use_api:
            try:
                self.api_client = PrimeAPIClient()
            except Exception as e:
                from rich.console import Console

                stderr_console = Console(stderr=True)
                stderr_console.print(
                    f"\n[yellow]⚠️  Warning:[/yellow] Failed to initialize API client: {e}"
                )
                stderr_console.print(
                    "[red]📉 Falling back to CLI parsing mode (degraded quality)[/red]"
                )
                stderr_console.print(
                    "   [dim]- GPU types may show as 'UNKNOWN' due to truncated output[/dim]"
                )
                stderr_console.print(
                    "   [dim]- Pricing data may be incomplete ($0.00 shown)[/dim]"
                )
                stderr_console.print(
                    "   [dim]- Results are limited by table width constraints[/dim]"
                )
                # Check if we can find prime in venv to give better instructions
                import os

                venv_prime = None
                if hasattr(sys, "prefix") and sys.prefix:
                    venv_prime_path = os.path.join(sys.prefix, "bin", "prime")
                    if os.path.exists(venv_prime_path):
                        venv_prime = venv_prime_path

                if venv_prime:
                    stderr_console.print(
                        f"\n[blue]💡 For best results, authenticate with:[/blue] [bold]{venv_prime} login[/bold]"
                    )
                    stderr_console.print(
                        "[blue]   Or simply run:[/blue] [bold]./prime-login.sh[/bold]\n"
                    )
                else:
                    stderr_console.print(
                        "\n[blue]💡 For best results, authenticate with:[/blue] [bold]prime login[/bold]\n"
                    )
                self.use_api = False

    def _parse_pod_status(self, status_str: str) -> PodStatus:
        """Safely parse pod status string to PodStatus enum."""
        try:
            return PodStatus(status_str.lower())  # type: ignore
        except ValueError:
            # Default to RUNNING if status is not recognized
            return PodStatus.RUNNING

    def _parse_gpu_type(self, gpu_type_str: str) -> GPUType:
        """Safely parse GPU type string to GPUType enum."""
        if not gpu_type_str:
            return GPUType.UNKNOWN

        # Extract the main GPU type (first part before any additional info)
        gpu_type_main = gpu_type_str.split()[0].upper()

        # Handle special cases
        if "CPU" in gpu_type_main:
            return GPUType.CPU

        # Try to match known GPU types
        for gpu_type in GPUType.__members__.values():
            if gpu_type.value == gpu_type_main:
                return gpu_type
            # Also try without underscores (e.g., RTX_4090 vs RTX4090)
            if gpu_type.value.replace("_", "") == gpu_type_main.replace("_", ""):
                return gpu_type

        # If no match found, return UNKNOWN
        return GPUType.UNKNOWN

    def _run_prime_command(
        self, command: List[str], retry_on_rate_limit: bool = True
    ) -> str:
        """Run a prime-cli command and return raw text output.

        Args:
            command: Command arguments to pass to prime-cli
            retry_on_rate_limit: Whether to retry on rate limit errors

        Returns:
            Raw text output from prime-cli

        Raises:
            RuntimeError: If command fails
        """
        # Try to find prime in the virtual environment first
        prime_cmd = "prime"
        if hasattr(sys, "prefix") and sys.prefix:
            venv_prime = os.path.join(sys.prefix, "bin", "prime")
            if os.path.exists(venv_prime):
                prime_cmd = venv_prime

        max_retries = 3 if retry_on_rate_limit else 1
        for attempt in range(max_retries):
            try:
                result = subprocess.run(
                    [prime_cmd] + command,
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=60,  # 60 second timeout
                )

                return result.stdout

            except FileNotFoundError:
                raise RuntimeError(
                    "prime-cli is not installed. Please install it with: pip install prime-cli"
                )
            except subprocess.TimeoutExpired:
                if attempt < max_retries - 1:
                    import time

                    time.sleep(2**attempt)  # Exponential backoff
                    continue
                else:
                    raise RuntimeError("Prime CLI command timed out")
            except subprocess.CalledProcessError as e:
                if e.stderr:
                    error_msg = e.stderr.strip()

                    # Check for authentication errors
                    if (
                        "Unauthorized" in error_msg
                        or "authentication" in error_msg.lower()
                    ):
                        raise RuntimeError(
                            "Not authenticated with prime-cli. Please run: prime login"
                        )

                    # Check for rate limiting
                    if (
                        "429" in error_msg
                        or "Too Many Requests" in error_msg
                        or "rate limit" in error_msg.lower()
                    ):
                        if attempt < max_retries - 1 and retry_on_rate_limit:
                            import time

                            delay = 5 * (2**attempt)  # 5, 10, 20 seconds
                            from rich.console import Console

                            stderr_console = Console(stderr=True)
                            stderr_console.print(
                                f"[yellow]Rate limited, waiting {delay}s before retry {attempt + 1}/{max_retries - 1}...[/yellow]"
                            )
                            time.sleep(delay)
                            continue
                        else:
                            raise RuntimeError(
                                "Rate limit exceeded. Please wait a few minutes before trying again."
                            )

                    # Check for specific error patterns
                    if "No GPU resources found" in error_msg:
                        raise RuntimeError(
                            "No GPU resources found matching your criteria"
                        )

                    # Generic error
                    raise RuntimeError(f"Prime CLI command failed: {error_msg}")
                else:
                    raise RuntimeError(
                        f"Prime CLI command failed with exit code {e.returncode}"
                    )

        # Should never reach here, but just in case
        raise RuntimeError("All retry attempts failed")

    def find_gpus(
        self,
        gpu_type: Optional[str] = None,
        min_count: int = 1,
        max_cost_per_hour: Optional[float] = None,
        regions: Optional[str] = None,
        provider: Optional[str] = None,
        include_free: bool = False,
    ) -> List[GPUResource]:
        """Find available GPU resources.

        Args:
            gpu_type: Specific GPU type to search for
            min_count: Minimum number of GPUs needed
            max_cost_per_hour: Maximum cost per hour per GPU (filtered locally)
            regions: Preferred regions filter (e.g., 'united_states')
            provider: Provider filter (e.g., 'aws', 'azure', 'google')
            include_free: Include $0.00 entries (default: False, filters them out)

        Returns:
            List of available GPU resources
        """
        # Try API first if available, but also get CLI data for correct IDs
        api_resources = []
        cli_resources = []

        if self.use_api and self.api_client:
            try:
                # Prepare region list
                region_list = None
                if regions:
                    region_list = [r.strip() for r in regions.split(",")]

                # Get data from API
                api_data = self.api_client.get_availability(
                    regions=region_list,
                    gpu_count=min_count if min_count > 1 else None,
                    gpu_type=gpu_type,
                )

                # Convert to GPUResource objects
                api_resources = self.api_client.to_gpu_resources(api_data)

            except Exception as e:
                from rich.console import Console

                stderr_console = Console(stderr=True)
                stderr_console.print(f"\n[yellow]⚠️  API call failed:[/yellow] {e}")
                stderr_console.print(
                    "[red]📉 Falling back to CLI parsing (degraded quality)[/red]"
                )

        # Always get CLI data for correct prime IDs (needed for pod creation)
        try:
            cmd = ["availability", "list"]
            if min_count > 1:
                cmd.extend(["--gpu-count", str(min_count)])
            if regions:
                cmd.extend(["--regions", regions])
            if provider:
                cmd.extend(["--provider", provider])

            output = self._run_prime_command(cmd)
            parsed_resources = parse_availability_table(output)

            # Convert CLI data to GPUResource objects
            for resource_data in parsed_resources:
                parsed_gpu_type = self._parse_gpu_type(resource_data["gpu_type"])

                if gpu_type and parsed_gpu_type.value != gpu_type:
                    continue

                if resource_data["available_count"] >= min_count:
                    if (
                        max_cost_per_hour is None
                        or resource_data["cost_per_hour"] <= max_cost_per_hour
                    ):
                        gpu_resource = GPUResource(
                            gpu_type=parsed_gpu_type,
                            available_count=resource_data["available_count"],
                            total_count=resource_data["total_count"],
                            cost_per_hour=resource_data["cost_per_hour"],
                            provider=resource_data["provider"],
                            region=resource_data["location"],
                            prime_id=resource_data[
                                "id"
                            ],  # This is the correct short ID
                        )
                        cli_resources.append(gpu_resource)

        except Exception as e:
            if not api_resources:  # Only fail if we don't have API fallback
                raise RuntimeError(f"Failed to get GPU data: {e}")

        # Use API resources if available (better data quality), but merge in CLI IDs
        if api_resources and cli_resources:
            # Try to match API resources with CLI resources to get correct IDs
            enhanced_resources = []
            for api_resource in api_resources:
                # Find matching CLI resource by GPU type and provider
                matching_cli = None
                for cli_resource in cli_resources:
                    if (
                        cli_resource.gpu_type == api_resource.gpu_type
                        and cli_resource.provider.lower()
                        == api_resource.provider.lower()
                    ):
                        matching_cli = cli_resource
                        break

                # Use API data but with CLI's correct prime_id
                if matching_cli:
                    api_resource.prime_id = matching_cli.prime_id

                enhanced_resources.append(api_resource)

            resources_to_filter = enhanced_resources
        elif api_resources:
            resources_to_filter = api_resources
        else:
            resources_to_filter = cli_resources

        # Apply local filters
        filtered = []
        for resource in resources_to_filter:
            # Filter by provider if specified
            if provider and provider.lower() not in resource.provider.lower():
                continue

            # Filter by max cost
            if max_cost_per_hour and resource.cost_per_hour > max_cost_per_hour:
                continue

            # Filter by availability
            if resource.available_count < min_count:
                continue

            # Filter out $0.00 entries (likely unavailable/placeholder) unless requested
            if not include_free and resource.cost_per_hour <= 0.0:
                continue

            filtered.append(resource)

        return filtered

    def create_pod_from_config(
        self,
        prime_id: str,
        name: Optional[str] = None,
        disk_size: int = 50,
        image: str = "pytorch/pytorch:2.0.1-cuda11.7-cudnn8-devel",
        **kwargs,
    ) -> Pod:
        """Create a new compute pod using a prime-cli configuration ID.

        Args:
            prime_id: Configuration ID from prime availability list
            name: Optional pod name
            disk_size: Disk size in GB (default: 50)
            image: Container image (default: PyTorch with CUDA)
            **kwargs: Additional pod configuration (stored as metadata)

        Returns:
            Created pod information
        """
        if name is None:
            name = f"pod-{uuid.uuid4().hex[:8]}"

        # Build command with all required parameters to avoid interactive prompts
        cmd = [
            "pods",
            "create",
            "--id",
            prime_id,
            "--name",
            name,
            "--disk-size",
            str(disk_size),
            "--image",
            image,
        ]

        # Add any additional parameters from kwargs
        if "vcpus" in kwargs:
            cmd.extend(["--vcpus", str(kwargs["vcpus"])])
        if "memory" in kwargs:
            cmd.extend(["--memory", str(kwargs["memory"])])
        if "gpu_count" in kwargs:
            cmd.extend(["--gpu-count", str(kwargs["gpu_count"])])
        if "team_id" in kwargs:
            cmd.extend(["--team-id", kwargs["team_id"]])

        # Add environment variables
        if "env" in kwargs and isinstance(kwargs["env"], dict):
            for key, value in kwargs["env"].items():
                cmd.extend(["--env", f"{key}={value}"])

        try:
            from rich.console import Console

            stderr_console = Console(stderr=True)
            stderr_console.print(f"[green]Creating pod with ID: {prime_id}[/green]")
            stderr_console.print(f"[dim]Command: prime {' '.join(cmd)}[/dim]")

            output = self._run_prime_command(cmd)

            # Parse the output to extract pod information
            # Look for pod ID in the output
            import re

            pod_id_match = re.search(r"Pod (\w+) created", output)
            if pod_id_match:
                pod_id = pod_id_match.group(1)
            else:
                # Fallback to generated ID if parsing fails
                pod_id = f"pod-{uuid.uuid4().hex[:12]}"

            # Try to extract more details from output
            gpu_type = GPUType.UNKNOWN
            gpu_count = kwargs.get("gpu_count", 1)
            cost_per_hour = 0.0
            provider = "Unknown"
            region = "Unknown"

            # Find the original resource to get accurate details
            try:
                resources = self.find_gpus(include_free=True)
                matching_resource = None
                for resource in resources:
                    if resource.prime_id == prime_id:
                        matching_resource = resource
                        break

                if matching_resource:
                    gpu_type = matching_resource.gpu_type
                    cost_per_hour = matching_resource.cost_per_hour
                    provider = matching_resource.provider
                    region = matching_resource.region

            except Exception:
                pass  # Use defaults if we can't find the resource

            # Create pod object
            pod = Pod(
                id=pod_id,
                name=name,
                status=PodStatus.CREATING,
                gpu_type=gpu_type,
                gpu_count=gpu_count,
                cost_per_hour=cost_per_hour,
                created_at=datetime.utcnow(),
                provider=provider,
                region=region,
                metadata={
                    "prime_id": prime_id,
                    "disk_size": disk_size,
                    "image": image,
                    **kwargs,
                },
            )

            self._pods[pod_id] = pod
            stderr_console.print(f"[green]✓ Pod {pod_id} created successfully![/green]")
            return pod

        except Exception as e:
            # Provide detailed error information
            error_msg = str(e)
            if "not found" in error_msg.lower() or "invalid" in error_msg.lower():
                raise RuntimeError(
                    f"Prime ID '{prime_id}' is not valid for pod creation. "
                    f"Try listing resources again to get a fresh ID. "
                    f"Original error: {e}"
                )
            elif "insufficient" in error_msg.lower() or "quota" in error_msg.lower():
                raise RuntimeError(
                    f"Insufficient resources or quota exceeded. Original error: {e}"
                )
            elif "auth" in error_msg.lower():
                raise RuntimeError(
                    f"Authentication failed. Please run 'prime login'. "
                    f"Original error: {e}"
                )
            else:
                raise RuntimeError(f"Failed to create pod: {e}")

    def create_pod(
        self,
        gpu_type: str,
        gpu_count: int = 1,
        name: Optional[str] = None,
        max_cost_per_hour: Optional[float] = None,
        regions: Optional[str] = None,
        **kwargs,
    ) -> Pod:
        """Create a pod by finding a suitable configuration first.

        Args:
            gpu_type: Type of GPU to request
            gpu_count: Number of GPUs
            name: Optional pod name
            max_cost_per_hour: Maximum acceptable cost per hour
            regions: Preferred regions filter
            **kwargs: Additional pod configuration

        Returns:
            Created pod information
        """
        # First, find available resources
        resources = self.find_gpus(
            gpu_type=gpu_type,
            min_count=gpu_count,
            max_cost_per_hour=max_cost_per_hour,
            regions=regions,
        )

        if not resources:
            raise RuntimeError(
                f"No available {gpu_type} resources found with {gpu_count} GPUs"
            )

        # Use the first (cheapest) available resource
        selected_resource = resources[0]

        if not selected_resource.prime_id:
            raise RuntimeError("Selected resource missing prime_id for pod creation")

        # Create pod using the configuration ID
        return self.create_pod_from_config(
            prime_id=selected_resource.prime_id, name=name, **kwargs
        )

    def get_pod_status(self, pod_id: str) -> Pod:
        """Get current status of a pod.

        Args:
            pod_id: Pod identifier

        Returns:
            Updated pod information
        """
        try:
            # Query prime-cli for actual pod status
            cmd = ["pods", "status", pod_id]
            output = self._run_prime_command(cmd)

            # Parse the detailed status output
            pod_info = self._parse_pod_status_output(output)

            # Check if we have this pod in our local cache
            if pod_id in self._pods:
                # Update cached pod with real status
                cached_pod = self._pods[pod_id]
                cached_pod.status = self._parse_pod_status(
                    pod_info.get("status", "unknown")
                )
                if pod_info.get("ssh_connection"):
                    cached_pod.ssh_connection = pod_info["ssh_connection"]
                if pod_info.get("started_at"):
                    cached_pod.started_at = pod_info["started_at"]
                if pod_info.get("stopped_at"):
                    cached_pod.stopped_at = pod_info["stopped_at"]
                return cached_pod
            else:
                # Create new pod object from status output
                pod = Pod(
                    id=pod_id,
                    name=pod_info.get("name", f"pod-{pod_id[:8]}"),
                    status=self._parse_pod_status(pod_info.get("status", "unknown")),
                    gpu_type=self._parse_gpu_type(pod_info.get("gpu_type", "")),
                    gpu_count=pod_info.get("gpu_count", 1),
                    cost_per_hour=pod_info.get("cost_per_hour", 0.0),
                    created_at=pod_info.get("created_at", datetime.utcnow()),
                    provider=pod_info.get("provider", "Unknown"),
                    region=pod_info.get("region", "Unknown"),
                    ssh_connection=pod_info.get("ssh_connection"),
                )

                if pod_info.get("started_at"):
                    pod.started_at = pod_info["started_at"]
                if pod_info.get("stopped_at"):
                    pod.stopped_at = pod_info["stopped_at"]

                # Cache the pod
                self._pods[pod_id] = pod
                return pod

        except Exception as e:
            # If prime-cli fails, check if we have cached data
            if pod_id in self._pods:
                return self._pods[pod_id]
            else:
                raise RuntimeError(
                    f"Failed to get pod status and no cached data available: {e}"
                )

    def _parse_pod_status_output(self, output: str) -> Dict[str, Any]:
        """Parse prime pods status command output."""
        pod_info = {}

        lines = output.strip().split("\n")
        for line in lines:
            line = line.strip()

            # Extract key-value pairs from status output
            if ":" in line and not line.startswith("┃") and not line.startswith("│"):
                key, value = line.split(":", 1)
                key = key.strip().lower().replace(" ", "_")
                value = value.strip()

                if key == "status":
                    pod_info["status"] = value
                elif key == "name" or key == "pod_name":
                    pod_info["name"] = value
                elif key == "gpu_type" or key == "gpu":
                    pod_info["gpu_type"] = value
                elif key == "gpu_count":
                    try:
                        pod_info["gpu_count"] = int(value)
                    except ValueError:
                        pod_info["gpu_count"] = 1
                elif key == "cost_per_hour" or key == "hourly_cost":
                    try:
                        # Remove $ and any other formatting
                        clean_value = (
                            value.replace("$", "").replace("/hour", "").strip()
                        )
                        pod_info["cost_per_hour"] = float(clean_value)
                    except ValueError:
                        pod_info["cost_per_hour"] = 0.0
                elif key == "provider":
                    pod_info["provider"] = value
                elif key == "region" or key == "location":
                    pod_info["region"] = value
                elif key == "ssh" or key == "ssh_connection":
                    pod_info["ssh_connection"] = value
                elif key == "created" or key == "created_at":
                    try:
                        # Try to parse datetime, fall back to current time
                        pod_info["created_at"] = datetime.fromisoformat(
                            value.replace("Z", "+00:00")
                        )
                    except ValueError:
                        pod_info["created_at"] = datetime.utcnow()

        return pod_info

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
                        region="Unknown",
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

    def ssh_to_pod(self, pod_id: str, interactive: bool = False) -> str:
        """Get SSH connection for a pod or launch interactive SSH session.

        Args:
            pod_id: Pod identifier
            interactive: If True, launch interactive SSH session

        Returns:
            SSH connection command or result of interactive session
        """
        try:
            # First check pod status
            pod = self.get_pod_status(pod_id)

            if pod.status != PodStatus.RUNNING:
                raise RuntimeError(
                    f"Pod {pod_id} is not running (current status: {pod.status.value})"
                )

            if interactive:
                # Launch interactive SSH session using prime-cli
                cmd = ["pods", "ssh", pod_id]

                from rich.console import Console

                stderr_console = Console(stderr=True)
                stderr_console.print(f"[green]Connecting to pod {pod_id}...[/green]")

                # Use subprocess.run without capture_output for interactive session
                import subprocess
                import sys

                # Try to find prime in the virtual environment first
                prime_cmd = "prime"
                if hasattr(sys, "prefix") and sys.prefix:
                    venv_prime = os.path.join(sys.prefix, "bin", "prime")
                    if os.path.exists(venv_prime):
                        prime_cmd = venv_prime

                result = subprocess.run([prime_cmd] + cmd)
                return f"SSH session to pod {pod_id} completed with exit code {result.returncode}"

            else:
                # Return SSH connection command
                if pod.ssh_connection:
                    return pod.ssh_connection
                else:
                    # Try to get SSH connection from prime-cli
                    try:
                        # Some versions of prime-cli might have a command to get SSH info
                        # For now, we'll construct a reasonable SSH command
                        return f"prime pods ssh {pod_id}"
                    except Exception:
                        raise RuntimeError(
                            f"SSH connection not available for pod {pod_id}"
                        )

        except Exception as e:
            if "not found" in str(e).lower():
                raise RuntimeError(f"Pod {pod_id} not found")
            else:
                raise RuntimeError(f"Failed to connect to pod {pod_id}: {e}")

    def get_pod_logs(self, pod_id: str, lines: int = 100) -> str:
        """Get logs from a pod.

        Args:
            pod_id: Pod identifier
            lines: Number of log lines to retrieve

        Returns:
            Pod logs
        """
        try:
            # Check if prime-cli has a logs command
            cmd = ["pods", "logs", pod_id, "--lines", str(lines)]
            output = self._run_prime_command(cmd)
            return output

        except Exception as e:
            # Fallback: try to get logs through SSH if available
            if "not found" in str(e).lower() or "command" in str(e).lower():
                raise RuntimeError(
                    f"Pod logs not available through prime-cli. "
                    f"Try SSH to pod and check logs manually: prime pods ssh {pod_id}"
                )
            else:
                raise RuntimeError(f"Failed to get pod logs: {e}")

