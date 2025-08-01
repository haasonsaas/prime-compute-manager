# Prime Compute Manager

A Python wrapper for [PrimeIntellect CLI](https://github.com/PrimeIntellect-ai/prime-cli) that provides an easy-to-use interface for managing GPU compute resources.

## Features

### 🔧 **Advanced Resource Management**
- **Advanced Filtering**: Filter by provider, cost range, minimum availability, and more
- **Intelligent Sorting**: Sort by cost, availability, utilization, GPU type, or provider
- **GPU Comparison Tool**: Side-by-side comparison with cost estimation for multiple time periods
- **Resource Discovery**: Find available GPU resources across 27+ GPU types and 500+ configurations

### 🖥️ **Complete Pod Operations**
- **Real Pod Status**: Parse actual prime-cli status output with detailed information
- **Interactive SSH**: Direct SSH session launch or command generation  
- **Pod Logs**: Retrieve pod logs with configurable line limits
- **Non-Interactive Creation**: Create pods with comprehensive parameters (disk, memory, environment)
- **Dry-Run Mode**: Preview pod configuration and costs before creation

### 🌐 **Multi-Pod Management (New!)**
- **Pod Configuration System**: Store and manage multiple pod configurations in `~/.pcm_config`
- **Active Pod Concept**: Switch between different managed pods with simple commands
- **SSH Automation**: Automatic SSH connection management and pod setup automation
- **Pod Setup Scripts**: One-command pod setup with automated script execution
- **Connection Testing**: Automatic SSH connection validation and pod health checks

*Multi-pod management inspired by the excellent [badlogic/pi](https://github.com/badlogic/pi) project*

### 🛡️ **Enterprise-Grade Reliability**
- **Rate Limiting**: Exponential backoff retry for both API and CLI calls
- **Timeout Handling**: 60-second timeouts with intelligent retry logic
- **Hybrid API/CLI**: Best data quality with valid pod creation IDs
- **Graceful Fallbacks**: API to CLI fallback with clear warnings
- **Specific Error Messages**: Authentication, rate limits, resource availability

### 🚀 **Production-Ready Features**
- **Type Safety**: Full type annotations and validation with Pydantic models
- **Cost Safety**: Dry-run mode and filtering protect against unexpected charges
- **Smart Caching**: Local pod caching with real-time status updates
- **Clean CLI**: Comprehensive command-line interface with JSON output support
- **Configuration Persistence**: Automatic migration of old config formats to new ones

> **Note**: This library provides a Python wrapper around the prime-cli tool. It parses prime-cli's table output and provides a more convenient API for managing GPU resources programmatically.

## Installation

### Quick Install (Recommended)

```bash
git clone https://github.com/haasonsaas/prime-compute-manager.git
cd prime-compute-manager
./install.sh
```

This one-click installer will:
- ✅ Set up a virtual environment
- ✅ Install all dependencies including Textual
- ✅ Create convenient launcher scripts
- ✅ Create a macOS app (on macOS)
- ✅ Test the installation

After installation, use the launcher:
```bash
./pcm-launcher.sh resources list   # List GPU resources
./pcm-launcher.sh pods create      # Create a pod
./pcm-launcher.sh pods list        # List active pods
```

### Manual Installation

```bash
pip install prime-compute-manager
```

Or install from source:

```bash
git clone https://github.com/haasonsaas/prime-compute-manager.git
cd prime-compute-manager
pip install -e ".[dev]"
```

See [INSTALL.md](INSTALL.md) for detailed installation instructions.

## Quick Start

### 1. Configure PrimeIntellect CLI

First, set up the prime-cli and log in:

```bash
pip install prime-cli
prime login  # Follow the authentication flow
```

**If you used the quick install**, prime-cli is already installed in the virtual environment. Use:

```bash
./prime-login.sh  # Helper script for authentication
```

Or directly:
```bash
./.venv/bin/prime login
```

### 2. Use Prime Compute Manager

```python
from prime_compute_manager import PrimeManager

# Initialize manager
manager = PrimeManager()

# Find available GPU configurations with advanced filtering
resources = manager.find_gpus(
    gpu_type="H100_80GB", 
    min_count=2,
    max_cost_per_hour=5.0,
    provider="runpod",
    include_free=False
)
print(f"Found {len(resources)} available configurations")

# Create a compute pod with comprehensive configuration
if resources:
    pod = manager.create_pod(
        gpu_type="H100_80GB",
        gpu_count=2,
        name="my-training-job",
        disk_size=100,
        memory=64,
        env={"CUDA_VISIBLE_DEVICES": "0,1", "PYTHONPATH": "/workspace"}
    )
    
    # Monitor pod status with detailed information
    status = manager.get_pod_status(pod.id)
    print(f"Pod {pod.name} status: {status.status}")
    
    # Get pod logs
    logs = manager.get_pod_logs(pod.id, lines=100)
    print(f"Recent logs:\n{logs}")
    
    # SSH connection (get command)
    ssh_cmd = manager.ssh_to_pod(pod.id)
    print(f"SSH command: {ssh_cmd}")
```

### 3. Multi-Pod Management (New!)

Prime Compute Manager now includes powerful multi-pod configuration management inspired by badlogic/pi:

#### Setup a Pod Configuration

```bash
# Configure a new pod with SSH connection
pcm pod setup my-gpu-server "root@192.168.1.100 -p 22"

# With automated setup script
pcm pod setup my-gpu-server "root@192.168.1.100 -p 22" --run-setup

# Skip connection testing (for temporarily unreachable pods)
pcm pod setup my-gpu-server "root@192.168.1.100 -p 22" --no-test-connection
```

#### Manage Pod Configurations

```bash
# List all configured pods
pcm pod list

# Switch between pods (sets active pod)
pcm pod switch my-gpu-server

# Check pod status and connectivity
pcm pod status

# Remove a pod configuration
pcm pod remove old-pod --yes
```

#### SSH and Remote Operations

```bash
# SSH into the active pod
pcm pod shell

# SSH to a specific pod
pcm pod shell --pod my-gpu-server

# Execute commands remotely
pcm pod ssh "nvidia-smi"
pcm pod ssh --interactive htop
pcm pod ssh --pod my-gpu-server "prime pods list"

# Check overall PCM status
pcm status
```

#### Pod Configuration File

PCM stores pod configurations in `~/.pcm_config`:

```json
{
  "active_pod": "my-gpu-server",
  "pods": {
    "my-gpu-server": {
      "name": "my-gpu-server",
      "ssh_command": "root@192.168.1.100 -p 22",
      "provider": "custom",
      "region": "my-server",
      "gpu_type": "RTX_4090",
      "gpu_count": 2,
      "cost_per_hour": 0.0,
      "created_at": "2024-01-01T12:00:00",
      "status": "configured"
    }
  },
  "version": "1.0"
}
```

#### Integration with Resource Management

```bash
# List resources and show active pod info
pcm resources list --show-active-pod

# Create pod and auto-configure it
pcm pods create --gpu-type H100_80GB --auto-configure

# The new pod will be added to your configuration automatically
```

### 4. Understanding the Workflow

Prime Compute Manager works by:

1. **Resource Discovery**: Using `prime availability list` to find available GPU configurations
2. **Configuration Selection**: Automatically selecting the best configuration based on your criteria
3. **Pod Creation**: Using `prime pods create --id <config_id>` to create pods with specific configurations
4. **Management**: Providing Python objects and methods to monitor and manage your resources

This abstraction allows you to work with GPU resources without needing to understand the underlying prime-cli table formats and configuration IDs.

### Command Line Interface

#### Resource Discovery & Filtering
```bash
# List available resources with advanced filtering
pcm resources list --gpu-type H100_80GB --provider runpod --max-cost 5.0

# Sort by availability (descending) and limit results
pcm resources list --sort-by availability --sort-desc --limit 10

# Filter by cost range and minimum availability
pcm resources list --min-cost 1.0 --max-cost 10.0 --min-availability 2

# Compare different GPU types with cost estimation
pcm resources compare --gpu-types "H100_80GB,A100_80GB,RTX_4090"
```

#### Pod Management
```bash
# Create a pod with comprehensive configuration
pcm pods create --gpu-type H100_80GB --count 2 --name training-job \
  --disk-size 100 --memory 64 --env CUDA_VISIBLE_DEVICES=0,1 --env PYTHONPATH=/workspace

# Preview pod creation (dry-run mode)
pcm pods create --gpu-type H100_80GB --dry-run

# List all pods with detailed information
pcm pods list --json

# Get detailed pod status
pcm pods status POD_ID

# Get pod logs
pcm pods logs POD_ID --lines 200

# SSH into a pod (interactive mode)
pcm pods ssh POD_ID --interactive

# Terminate a pod
pcm pods terminate POD_ID --yes
```

#### JSON Output for Automation
```bash
# Get resources as JSON for scripting
pcm resources list --json | jq '.[] | select(.cost_per_hour < 5.0)'

# Compare resources with JSON output
pcm resources compare --gpu-types "H100_80GB,A100_80GB" --json
```


## Configuration

Create a `config.yaml` file:

```yaml
prime_cli:
  api_key: your_api_key_here
  team: your_team_name

default_settings:
  gpu_type: H100_80GB
  max_cost_per_hour: 10.0
  auto_terminate_hours: 24

notifications:
  webhook_url: https://your-webhook.com/notify
  email: your-email@example.com
```

## Advanced Examples

### Resource Comparison and Cost Analysis

```python
from prime_compute_manager import PrimeManager

manager = PrimeManager()

# Compare different GPU types for cost optimization
gpu_types = ["H100_80GB", "A100_80GB", "RTX_4090"]
comparison = {}

for gpu_type in gpu_types:
    resources = manager.find_gpus(
        gpu_type=gpu_type,
        min_count=1,
        max_cost_per_hour=10.0,
        include_free=False
    )
    
    if resources:
        cheapest = min(resources, key=lambda r: r.cost_per_hour)
        comparison[gpu_type] = {
            "best_price": cheapest.cost_per_hour,
            "provider": cheapest.provider,
            "availability": cheapest.available_count,
            "daily_cost": cheapest.cost_per_hour * 24
        }

print("GPU Cost Comparison:")
for gpu_type, data in comparison.items():
    print(f"{gpu_type}: ${data['best_price']:.2f}/hr (${data['daily_cost']:.2f}/day) from {data['provider']}")
```

### Smart Pod Management with Error Handling

```python
from prime_compute_manager import PrimeManager
import time

def create_pod_with_retry(manager, gpu_type, max_retries=3):
    """Create a pod with intelligent retry logic."""
    
    for attempt in range(max_retries):
        try:
            # Find available resources
            resources = manager.find_gpus(
                gpu_type=gpu_type,
                min_count=1,
                max_cost_per_hour=8.0,
                include_free=False
            )
            
            if not resources:
                print(f"No {gpu_type} resources available, trying again in 30s...")
                time.sleep(30)
                continue
            
            # Create pod with comprehensive configuration
            pod = manager.create_pod(
                gpu_type=gpu_type,
                gpu_count=1,
                name=f"training-{int(time.time())}",
                disk_size=100,
                image="pytorch/pytorch:2.0.1-cuda11.7-cudnn8-devel",
                env={
                    "WANDB_API_KEY": "your-wandb-key",
                    "CUDA_VISIBLE_DEVICES": "0"
                }
            )
            
            print(f"Pod {pod.id} created successfully!")
            return pod
            
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                print("Retrying in 60 seconds...")
                time.sleep(60)
    
    raise RuntimeError(f"Failed to create pod after {max_retries} attempts")

# Usage
manager = PrimeManager()
try:
    pod = create_pod_with_retry(manager, "H100_80GB")
    
    # Monitor pod until running
    while True:
        status = manager.get_pod_status(pod.id)
        print(f"Pod status: {status.status.value}")
        
        if status.status.value == "running":
            print(f"Pod is ready! SSH: {manager.ssh_to_pod(pod.id)}")
            break
        elif status.status.value == "failed":
            print("Pod failed to start")
            break
            
        time.sleep(10)
        
except Exception as e:
    print(f"Pod creation failed: {e}")
```

### Automated Resource Discovery and Filtering

```python
from prime_compute_manager import PrimeManager

def find_best_value_gpu(manager, min_gpu_memory_gb=24):
    """Find the best value GPU with sufficient memory."""
    
    # GPU types with their approximate memory
    gpu_memory_map = {
        "H100_80GB": 80,
        "A100_80GB": 80,
        "A100_40GB": 40,
        "RTX_A6000": 48,
        "RTX_4090": 24,
        "V100_32GB": 32
    }
    
    best_deals = []
    
    for gpu_type, memory_gb in gpu_memory_map.items():
        if memory_gb < min_gpu_memory_gb:
            continue
            
        resources = manager.find_gpus(
            gpu_type=gpu_type,
            min_count=1,
            include_free=False
        )
        
        if resources:
            cheapest = min(resources, key=lambda r: r.cost_per_hour)
            value_score = memory_gb / cheapest.cost_per_hour  # GB per dollar per hour
            
            best_deals.append({
                "gpu_type": gpu_type,
                "cost_per_hour": cheapest.cost_per_hour,
                "memory_gb": memory_gb,
                "value_score": value_score,
                "provider": cheapest.provider,
                "availability": cheapest.available_count
            })
    
    # Sort by value score (descending)
    best_deals.sort(key=lambda x: x["value_score"], reverse=True)
    
    print(f"Best value GPUs with ≥{min_gpu_memory_gb}GB memory:")
    for deal in best_deals[:5]:
        print(f"{deal['gpu_type']}: ${deal['cost_per_hour']:.2f}/hr "
              f"({deal['memory_gb']}GB, {deal['value_score']:.1f} GB/$·hr) "
              f"from {deal['provider']}")
    
    return best_deals[0] if best_deals else None

# Usage
manager = PrimeManager()
best_gpu = find_best_value_gpu(manager, min_gpu_memory_gb=40)

if best_gpu:
    print(f"\nCreating pod with best value GPU: {best_gpu['gpu_type']}")
    # Proceed with pod creation...
```

## Development

```bash
# Clone repository
git clone https://github.com/haasonsaas/prime-compute-manager.git
cd prime-compute-manager

# Install development dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Run tests
pytest

# Run linting
ruff check .
black .
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'feat: add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built on top of [PrimeIntellect CLI](https://github.com/PrimeIntellect-ai/prime-cli)
- Multi-pod management system inspired by [badlogic/pi](https://github.com/badlogic/pi)
- Inspired by the need for better GPU resource management