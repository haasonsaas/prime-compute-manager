"""SSH connection management for Prime Compute Manager."""

import subprocess
import shlex
import os
from typing import Optional, Union
from .config import ConfigManager, PodConfig


class SSHManager:
    """Manages SSH connections to pods."""

    def __init__(self, config_manager: ConfigManager):
        """Initialize SSH manager.

        Args:
            config_manager: Configuration manager instance
        """
        self.config_manager = config_manager

    def _validate_ssh_command(self, ssh_command: str) -> str:
        """Validate and clean SSH command.

        Args:
            ssh_command: Raw SSH command

        Returns:
            Cleaned SSH command
        """
        # Remove 'ssh' prefix if present
        if ssh_command.lower().startswith("ssh "):
            ssh_command = ssh_command[4:].strip()

        # Basic validation - should have user@host format
        if "@" not in ssh_command.split()[0]:
            raise ValueError("SSH command must include user@host format")

        return ssh_command

    def test_ssh_connection(self, ssh_command: str) -> bool:
        """Test SSH connection to a pod.

        Args:
            ssh_command: SSH connection command

        Returns:
            True if connection successful
        """
        try:
            cleaned_cmd = self._validate_ssh_command(ssh_command)

            # Test with a simple hostname command
            result = subprocess.run(
                f'ssh {cleaned_cmd} "hostname"',
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
            )

            return result.returncode == 0

        except Exception:
            return False

    def execute_ssh_command(
        self,
        pod_config: PodConfig,
        command: str,
        interactive: bool = False,
        timeout: Optional[int] = None,
    ) -> Union[str, int]:
        """Execute a command on a pod via SSH.

        Args:
            pod_config: Pod configuration
            command: Command to execute
            interactive: Whether to run in interactive mode
            timeout: Command timeout in seconds

        Returns:
            Command output (non-interactive) or exit code (interactive)
        """
        ssh_cmd = f"ssh {pod_config.ssh_command} {shlex.quote(command)}"

        if interactive:
            # For interactive commands, use subprocess with inherit stdio
            result = subprocess.run(ssh_cmd, shell=True)
            return result.returncode
        else:
            # For non-interactive, capture output
            result = subprocess.run(
                ssh_cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout or 60,
            )

            if result.returncode != 0:
                raise RuntimeError(f"SSH command failed: {result.stderr}")

            return result.stdout

    def launch_ssh_session(self, pod_config: PodConfig) -> int:
        """Launch an interactive SSH session.

        Args:
            pod_config: Pod configuration

        Returns:
            Exit code
        """
        ssh_cmd = f"ssh {pod_config.ssh_command}"
        result = subprocess.run(ssh_cmd, shell=True)
        return result.returncode

    def copy_file_to_pod(
        self, pod_config: PodConfig, local_path: str, remote_path: str = "~/"
    ) -> None:
        """Copy a file to a pod using SCP.

        Args:
            pod_config: Pod configuration
            local_path: Local file path
            remote_path: Remote destination path
        """
        # Parse SSH command to extract connection details
        ssh_parts = pod_config.ssh_command.split()
        user_host = ssh_parts[0]

        # Build SCP command
        scp_cmd = ["scp"]

        # Add port if specified in SSH command
        if "-p" in ssh_parts:
            port_idx = ssh_parts.index("-p")
            if port_idx + 1 < len(ssh_parts):
                port = ssh_parts[port_idx + 1]
                scp_cmd.extend(["-P", port])

        # Add other SSH options if needed
        for i, part in enumerate(ssh_parts):
            if part == "-i" and i + 1 < len(ssh_parts):
                scp_cmd.extend(["-i", ssh_parts[i + 1]])

        scp_cmd.extend([local_path, f"{user_host}:{remote_path}"])

        result = subprocess.run(scp_cmd)
        if result.returncode != 0:
            raise RuntimeError(f"SCP failed with exit code {result.returncode}")

    def copy_files_to_pod(
        self, pod_config: PodConfig, files: dict, remote_base_path: str = "~/"
    ) -> None:
        """Copy multiple files to a pod.

        Args:
            pod_config: Pod configuration
            files: Dictionary of {local_path: remote_filename}
            remote_base_path: Base directory on remote host
        """
        for local_path, remote_filename in files.items():
            if not os.path.exists(local_path):
                raise FileNotFoundError(f"Local file not found: {local_path}")

            remote_path = f"{remote_base_path.rstrip('/')}/{remote_filename}"
            self.copy_file_to_pod(pod_config, local_path, remote_path)

    def get_pod_hostname(self, pod_config: PodConfig) -> str:
        """Get the hostname of a pod.

        Args:
            pod_config: Pod configuration

        Returns:
            Pod hostname
        """
        try:
            output = self.execute_ssh_command(pod_config, "hostname", timeout=10)
            return output.strip()
        except Exception as e:
            raise RuntimeError(f"Failed to get pod hostname: {e}")

    def check_pod_status(self, pod_config: PodConfig) -> dict:
        """Check various status information about a pod.

        Args:
            pod_config: Pod configuration

        Returns:
            Dictionary with status information
        """
        status = {}

        try:
            # Get basic system info
            hostname = self.get_pod_hostname(pod_config)
            status["hostname"] = hostname
            status["reachable"] = True

            # Check if prime-cli is available
            try:
                prime_check = self.execute_ssh_command(
                    pod_config, "which prime || echo 'not found'", timeout=10
                )
                status["prime_cli_available"] = "not found" not in prime_check
            except:
                status["prime_cli_available"] = False

            # Check GPU availability if nvidia-smi is available
            try:
                gpu_info = self.execute_ssh_command(
                    pod_config,
                    "nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null || echo 'no gpus'",
                    timeout=15,
                )
                if "no gpus" not in gpu_info.lower():
                    status["gpus"] = [
                        gpu.strip()
                        for gpu in gpu_info.strip().split("\n")
                        if gpu.strip()
                    ]
                else:
                    status["gpus"] = []
            except:
                status["gpus"] = []

            # Check system load
            try:
                uptime = self.execute_ssh_command(pod_config, "uptime", timeout=10)
                status["uptime"] = uptime.strip()
            except:
                status["uptime"] = "unknown"

        except Exception as e:
            status["reachable"] = False
            status["error"] = str(e)

        return status

