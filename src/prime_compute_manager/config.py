"""Configuration management for Prime Compute Manager."""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from .models import PodStatus


@dataclass
class PodConfig:
    """Configuration for a managed pod."""

    name: str
    ssh_command: str
    provider: str
    region: str
    gpu_type: str
    gpu_count: int
    cost_per_hour: float
    created_at: str
    pod_id: Optional[str] = None
    status: str = "unknown"
    setup_script: Optional[str] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class PCMConfig:
    """Prime Compute Manager configuration."""

    active_pod: Optional[str] = None
    pods: Dict[str, PodConfig] = None
    version: str = "1.0"

    def __post_init__(self):
        if self.pods is None:
            self.pods = {}


class ConfigManager:
    """Manages PCM configuration file (~/.pcm_config)."""

    def __init__(self, config_path: Optional[str] = None):
        """Initialize config manager.

        Args:
            config_path: Optional custom config path, defaults to ~/.pcm_config
        """
        if config_path:
            self.config_path = Path(config_path)
        else:
            self.config_path = Path.home() / ".pcm_config"

        self._config: Optional[PCMConfig] = None
        self._load_config()

    def _load_config(self) -> None:
        """Load configuration from file."""
        if not self.config_path.exists():
            self._config = PCMConfig()
            self._save_config()
            return

        try:
            with open(self.config_path, "r") as f:
                data = json.load(f)

            # Convert pod configs from dict to PodConfig objects
            pods = {}
            if "pods" in data and data["pods"]:
                for name, pod_data in data["pods"].items():
                    pods[name] = PodConfig(**pod_data)

            self._config = PCMConfig(
                active_pod=data.get("active_pod"),
                pods=pods,
                version=data.get("version", "1.0"),
            )

            # Migrate old config format if needed
            self._migrate_config()

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            # Backup corrupted config and create new one
            if self.config_path.exists():
                backup_path = self.config_path.with_suffix(".backup")
                self.config_path.rename(backup_path)
                print(f"Warning: Corrupted config backed up to {backup_path}")

            self._config = PCMConfig()
            self._save_config()

    def _migrate_config(self) -> None:
        """Migrate old config formats to current version."""
        if not self._config:
            return

        # Future migration logic would go here
        # For now, just ensure we have the current version
        if self._config.version != "1.0":
            self._config.version = "1.0"
            self._save_config()

    def _save_config(self) -> None:
        """Save configuration to file."""
        if not self._config:
            return

        # Convert to dict for JSON serialization
        data = {
            "active_pod": self._config.active_pod,
            "pods": {name: asdict(pod) for name, pod in self._config.pods.items()},
            "version": self._config.version,
        }

        # Ensure parent directory exists
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        # Write to temp file first, then rename for atomicity
        temp_path = self.config_path.with_suffix(".tmp")
        try:
            with open(temp_path, "w") as f:
                json.dump(data, f, indent=2)
            temp_path.rename(self.config_path)
        except Exception as e:
            if temp_path.exists():
                temp_path.unlink()
            raise RuntimeError(f"Failed to save config: {e}")

    @property
    def config(self) -> PCMConfig:
        """Get current configuration."""
        if not self._config:
            self._load_config()
        return self._config

    def add_pod(self, name: str, ssh_command: str, **kwargs) -> None:
        """Add a new pod configuration.

        Args:
            name: Pod name
            ssh_command: SSH connection command
            **kwargs: Additional pod configuration
        """
        if name in self.config.pods:
            raise ValueError(f"Pod '{name}' already exists")

        pod_config = PodConfig(
            name=name,
            ssh_command=ssh_command,
            provider=kwargs.get("provider", "unknown"),
            region=kwargs.get("region", "unknown"),
            gpu_type=kwargs.get("gpu_type", "unknown"),
            gpu_count=kwargs.get("gpu_count", 1),
            cost_per_hour=kwargs.get("cost_per_hour", 0.0),
            created_at=datetime.utcnow().isoformat(),
            pod_id=kwargs.get("pod_id"),
            status=kwargs.get("status", "unknown"),
            setup_script=kwargs.get("setup_script"),
            metadata=kwargs.get("metadata", {}),
        )

        self.config.pods[name] = pod_config

        # Set as active pod if it's the first one
        if not self.config.active_pod:
            self.config.active_pod = name

        self._save_config()

    def remove_pod(self, name: str) -> None:
        """Remove a pod configuration.

        Args:
            name: Pod name to remove
        """
        if name not in self.config.pods:
            raise ValueError(f"Pod '{name}' not found")

        del self.config.pods[name]

        # Clear active pod if it was the removed one
        if self.config.active_pod == name:
            # Set to first available pod or None
            self.config.active_pod = next(iter(self.config.pods.keys()), None)

        self._save_config()

    def set_active_pod(self, name: str) -> None:
        """Set the active pod.

        Args:
            name: Pod name to set as active
        """
        if name not in self.config.pods:
            raise ValueError(f"Pod '{name}' not found")

        self.config.active_pod = name
        self._save_config()

    def get_active_pod(self) -> Optional[PodConfig]:
        """Get the active pod configuration."""
        if not self.config.active_pod or self.config.active_pod not in self.config.pods:
            return None
        return self.config.pods[self.config.active_pod]

    def get_pod(self, name: str) -> Optional[PodConfig]:
        """Get a specific pod configuration.

        Args:
            name: Pod name

        Returns:
            Pod configuration or None if not found
        """
        return self.config.pods.get(name)

    def list_pods(self) -> List[PodConfig]:
        """List all pod configurations."""
        return list(self.config.pods.values())

    def update_pod_status(
        self, name: str, status: str, pod_id: Optional[str] = None
    ) -> None:
        """Update pod status.

        Args:
            name: Pod name
            status: New status
            pod_id: Optional pod ID to update
        """
        if name not in self.config.pods:
            raise ValueError(f"Pod '{name}' not found")

        self.config.pods[name].status = status
        if pod_id:
            self.config.pods[name].pod_id = pod_id

        self._save_config()

    def get_config_path(self) -> Path:
        """Get the configuration file path."""
        return self.config_path

    def backup_config(self) -> Path:
        """Create a backup of the current configuration.

        Returns:
            Path to the backup file
        """
        if not self.config_path.exists():
            raise RuntimeError("No configuration file to backup")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.config_path.with_suffix(f".backup_{timestamp}")

        import shutil

        shutil.copy2(self.config_path, backup_path)

        return backup_path

