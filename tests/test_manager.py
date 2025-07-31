"""Tests for PrimeManager class."""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from prime_compute_manager.manager import PrimeManager
from prime_compute_manager.models import GPUResource, Pod, GPUType, PodStatus


class TestPrimeManager:
    """Test cases for PrimeManager."""
    
    manager: PrimeManager
    
    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.manager = PrimeManager()
    
    @patch('prime_compute_manager.manager.subprocess.run')
    def test_find_gpus_success(self, mock_run):
        """Test successful GPU resource discovery."""
        # Mock subprocess response
        mock_result = Mock()
        mock_result.stdout = '{"resources": []}'
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        
        resources = self.manager.find_gpus(
            gpu_type="H100_80GB",
            min_count=2,
            max_cost_per_hour=5.0
        )
        
        assert isinstance(resources, list)
        # Should return mock data since prime-cli output parsing is mocked
        assert len(resources) >= 0
    
    @patch('prime_compute_manager.manager.subprocess.run')
    def test_find_gpus_command_failure(self, mock_run):
        """Test GPU discovery with command failure."""
        # Mock subprocess failure
        mock_run.side_effect = Exception("Command failed")
        
        with pytest.raises(RuntimeError, match="Failed to find GPUs"):
            self.manager.find_gpus(gpu_type="H100_80GB")
    
    @patch('prime_compute_manager.manager.subprocess.run')
    def test_create_pod_success(self, mock_run):
        """Test successful pod creation."""
        # Mock subprocess response
        mock_result = Mock()
        mock_result.stdout = '{"pod_id": "test-pod-123"}'
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        
        pod = self.manager.create_pod(
            gpu_type="H100_80GB",
            gpu_count=2,
            name="test-pod"
        )
        
        assert isinstance(pod, Pod)
        assert pod.name == "test-pod"
        assert pod.gpu_type == GPUType.H100_80GB
        assert pod.gpu_count == 2
        assert pod.status == PodStatus.CREATING
        assert pod.id in self.manager._pods
    
    def test_create_pod_auto_name(self):
        """Test pod creation with auto-generated name."""
        with patch('prime_compute_manager.manager.subprocess.run') as mock_run:
            mock_result = Mock()
            mock_result.stdout = '{"pod_id": "test-pod-123"}'
            mock_run.return_value = mock_result
            
            pod = self.manager.create_pod(
                gpu_type="H100_80GB",
                gpu_count=1
            )
            
            assert pod.name.startswith("pod-")
            assert len(pod.name) > 4  # "pod-" + uuid part
    
    def test_get_pod_status_not_found(self):
        """Test getting status of non-existent pod."""
        with pytest.raises(ValueError, match="Pod nonexistent not found"):
            self.manager.get_pod_status("nonexistent")
    
    def test_get_pod_status_existing(self):
        """Test getting status of existing pod."""
        # Create a mock pod
        with patch('prime_compute_manager.manager.subprocess.run') as mock_run:
            mock_result = Mock()
            mock_result.stdout = '{"pod_id": "test-pod-123"}'
            mock_run.return_value = mock_result
            
            pod = self.manager.create_pod(
                gpu_type="H100_80GB",
                gpu_count=1,
                name="test-pod"
            )
            
            # Get status (should update to running in mock)
            updated_pod = self.manager.get_pod_status(pod.id)
            
            assert updated_pod.id == pod.id
            assert updated_pod.status == PodStatus.RUNNING  # Mock updates to running
            assert updated_pod.ssh_connection is not None
    
    @patch('prime_compute_manager.manager.subprocess.run')
    def test_list_pods_empty(self, mock_run):
        """Test listing pods when none exist."""
        mock_result = Mock()
        mock_result.stdout = '{"pods": []}'
        mock_run.return_value = mock_result
        
        pods = self.manager.list_pods()
        assert pods == []
    
    def test_list_pods_with_pods(self):
        """Test listing pods with existing pods."""
        # Create some mock pods
        with patch('prime_compute_manager.manager.subprocess.run') as mock_run:
            mock_result = Mock()
            mock_result.stdout = '{"pod_id": "test-pod-123"}'
            mock_run.return_value = mock_result
            
            pod1 = self.manager.create_pod(gpu_type="H100_80GB", gpu_count=1, name="pod1")
            pod2 = self.manager.create_pod(gpu_type="A100_80GB", gpu_count=2, name="pod2")
            
            # List active pods
            active_pods = self.manager.list_pods(active_only=True)
            assert len(active_pods) == 2
            
            # List all pods
            all_pods = self.manager.list_pods(active_only=False)
            assert len(all_pods) == 2
    
    def test_terminate_pod_not_found(self):
        """Test terminating non-existent pod."""
        with pytest.raises(ValueError, match="Pod nonexistent not found"):
            self.manager.terminate_pod("nonexistent")
    
    def test_terminate_pod_success(self):
        """Test successful pod termination."""
        # Create a mock pod first
        with patch('prime_compute_manager.manager.subprocess.run') as mock_run:
            mock_result = Mock()
            mock_result.stdout = '{"pod_id": "test-pod-123"}'
            mock_run.return_value = mock_result
            
            pod = self.manager.create_pod(
                gpu_type="H100_80GB",
                gpu_count=1,
                name="test-pod"
            )
            
            # Terminate the pod
            success = self.manager.terminate_pod(pod.id)
            
            assert success is True
            
            # Check that pod status was updated
            terminated_pod = self.manager._pods[pod.id]
            assert terminated_pod.status == PodStatus.STOPPED
            assert terminated_pod.stopped_at is not None
    
    def test_ssh_to_pod_not_running(self):
        """Test SSH to pod that's not running."""
        # Create a mock pod that's not running
        with patch('prime_compute_manager.manager.subprocess.run') as mock_run:
            mock_result = Mock()
            mock_result.stdout = '{"pod_id": "test-pod-123"}'
            mock_run.return_value = mock_result
            
            pod = self.manager.create_pod(
                gpu_type="H100_80GB",
                gpu_count=1,
                name="test-pod"
            )
            
            # Mock get_pod_status to return a pod that's still creating
            with patch.object(self.manager, 'get_pod_status') as mock_status:
                creating_pod = Pod(
                    id=pod.id,
                    name=pod.name,
                    status=PodStatus.CREATING,
                    gpu_type=pod.gpu_type,
                    gpu_count=pod.gpu_count,
                    cost_per_hour=pod.cost_per_hour,
                    created_at=pod.created_at,
                    provider=pod.provider,
                    region=pod.region
                )
                mock_status.return_value = creating_pod
                
                with pytest.raises(RuntimeError, match="Pod .* is not running"):
                    self.manager.ssh_to_pod(pod.id)
    
    def test_ssh_to_pod_running(self):
        """Test SSH to running pod."""
        # Create and "start" a mock pod
        with patch('prime_compute_manager.manager.subprocess.run') as mock_run:
            mock_result = Mock()
            mock_result.stdout = '{"pod_id": "test-pod-123"}'
            mock_run.return_value = mock_result
            
            pod = self.manager.create_pod(
                gpu_type="H100_80GB",
                gpu_count=1,
                name="test-pod"
            )
            
            # Get status to trigger mock update to running
            updated_pod = self.manager.get_pod_status(pod.id)
            
            # Now SSH should work
            ssh_cmd = self.manager.ssh_to_pod(pod.id)
            
            assert ssh_cmd is not None
            assert ssh_cmd.startswith("ssh")