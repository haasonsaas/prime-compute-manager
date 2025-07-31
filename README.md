# Prime Compute Manager

A Python wrapper for [PrimeIntellect CLI](https://github.com/PrimeIntellect-ai/prime-cli) that provides an easy-to-use interface for managing GPU compute resources.

## Features

- 🔍 **Resource Discovery**: Find available GPU resources across providers with automatic table parsing
- 🚀 **Pod Management**: Create, monitor, and manage compute pods using real prime-cli integration
- 📊 **Usage Monitoring**: Track resource usage and costs  
- 🔧 **Easy Integration**: Simple Python API that wraps prime-cli commands
- 🛡️ **Type Safety**: Full type annotations and validation with Pydantic models

> **Note**: This library provides a Python wrapper around the prime-cli tool. It parses prime-cli's table output and provides a more convenient API for managing GPU resources programmatically.

## Installation

```bash
pip install prime-compute-manager
```

Or install from source:

```bash
git clone https://github.com/haasonsaas/prime-compute-manager.git
cd prime-compute-manager
pip install -e ".[dev]"
```

## Quick Start

### 1. Configure PrimeIntellect CLI

First, set up the prime-cli and log in:

```bash
pip install prime-cli
prime login  # Follow the authentication flow
```

### 2. Use Prime Compute Manager

```python
from prime_compute_manager import PrimeManager

# Initialize manager
manager = PrimeManager()

# Find available GPU configurations
resources = manager.find_gpus(gpu_type="H100_80GB", min_count=2)
print(f"Found {len(resources)} available configurations")

# Create a compute pod using the first available configuration
if resources:
    pod = manager.create_pod(
        gpu_type="H100_80GB",
        gpu_count=2,
        name="my-training-job"
    )
    
    # Monitor pod status
    status = manager.get_pod_status(pod.id)
    print(f"Pod {pod.name} status: {status.status}")
```

### 3. Understanding the Workflow

Prime Compute Manager works by:

1. **Resource Discovery**: Using `prime availability list` to find available GPU configurations
2. **Configuration Selection**: Automatically selecting the best configuration based on your criteria
3. **Pod Creation**: Using `prime pods create --id <config_id>` to create pods with specific configurations
4. **Management**: Providing Python objects and methods to monitor and manage your resources

This abstraction allows you to work with GPU resources without needing to understand the underlying prime-cli table formats and configuration IDs.

### Command Line Interface

```bash
# List available resources
pcm resources list --gpu-type H100_80GB

# Create a pod
pcm pods create --gpu-type H100_80GB --count 2 --name training-job

# Monitor pods
pcm pods status

# SSH into a pod
pcm pods ssh POD_ID
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

## Examples

### Batch Job Processing

```python
import asyncio
from prime_compute_manager import PrimeManager, JobQueue

async def main():
    manager = PrimeManager()
    queue = JobQueue(manager)
    
    # Add jobs to queue
    jobs = [
        {"script": "train_model.py", "args": {"epochs": 100}},
        {"script": "evaluate.py", "args": {"model_path": "/models/best.pt"}},
    ]
    
    for job in jobs:
        queue.add_job(job)
    
    # Process jobs
    await queue.process_all()

if __name__ == "__main__":
    asyncio.run(main())
```

### Resource Monitoring

```python
from prime_compute_manager import ResourceMonitor

monitor = ResourceMonitor()

# Get current usage
usage = monitor.get_team_usage()
print(f"Current cost: ${usage.current_cost_per_hour:.2f}/hour")

# Set up alerts
monitor.add_alert(
    condition="cost_per_hour > 50",
    action="email",
    recipient="admin@company.com"
)

# Start monitoring
monitor.start()
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
- Inspired by the need for better GPU resource management