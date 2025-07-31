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
    @patch('prime_compute_manager.manager.parse_availability_table')
    def test_find_gpus_success(self, mock_parser, mock_run):
        """Test successful GPU resource discovery."""
        # Mock subprocess response with table output
        mock_result = Mock()
        mock_result.stdout = 'mock table output'
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        
        # Mock parser to return fake resource data
        mock_parser.return_value = [
            {
                'id': 'test-config-1',
                'gpu_type': 'H100_80GB',
                'gpu_count': 2,
                'provider': 'AWS',
                'location': 'us-west-2',
                'cost_per_hour': 4.0,
                'available_count': 2,
                'total_count': 2,
                'vcpus': 64,
                'ram_gb': 256,
                'disk_gb': 1000,
                'socket': 'socket1',
                'availability': 'available'
            }
        ]
        
        resources = self.manager.find_gpus(
            gpu_type="H100_80GB",
            min_count=2,
            max_cost_per_hour=5.0
        )
        
        assert isinstance(resources, list)
        assert len(resources) == 1
        assert resources[0].gpu_type == GPUType.H100_80GB
        assert resources[0].prime_id == 'test-config-1'
    
    @patch('prime_compute_manager.manager.subprocess.run')
    def test_find_gpus_command_failure(self, mock_run):
        """Test GPU discovery with command failure."""
        # Mock subprocess failure
        mock_run.side_effect = Exception("Command failed")
        
        with pytest.raises(RuntimeError, match="Failed to find GPUs"):
            self.manager.find_gpus(gpu_type="H100_80GB")
    
    @patch('prime_compute_manager.manager.subprocess.run')
    @patch('prime_compute_manager.manager.parse_availability_table')
    def test_create_pod_success(self, mock_parser, mock_run):
        """Test successful pod creation."""
        # Mock subprocess response
        mock_result = Mock()
        mock_result.stdout = 'mock table output'
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        
        # Mock parser to return available resources for find_gpus
        mock_parser.return_value = [
            {
                'id': 'test-config-1',
                'gpu_type': 'H100_80GB',
                'gpu_count': 2,
                'provider': 'AWS',
                'location': 'us-west-2',
                'cost_per_hour': 4.0,
                'available_count': 2,
                'total_count': 2,
                'vcpus': 64,
                'ram_gb': 256,
                'disk_gb': 1000,
                'socket': 'socket1',
                'availability': 'available'
            }
        ]
        
        pod = self.manager.create_pod(
            gpu_type="H100_80GB",
            gpu_count=2,
            name="test-pod"
        )
        
        assert isinstance(pod, Pod)
        assert pod.name == "test-pod"
        assert pod.gpu_type == GPUType.H100_80GB
        assert pod.gpu_count == 1  # This comes from the mocked pod creation
        assert pod.status == PodStatus.CREATING
        assert pod.id in self.manager._pods
    
    @patch('prime_compute_manager.manager.parse_availability_table')
    def test_create_pod_auto_name(self, mock_parser):
        """Test pod creation with auto-generated name."""
        with patch('prime_compute_manager.manager.subprocess.run') as mock_run:
            mock_result = Mock()
            mock_result.stdout = 'mock table output'
            mock_run.return_value = mock_result
            
            # Mock parser to return available resources
            mock_parser.return_value = [
                {
                    'id': 'test-config-1',
                    'gpu_type': 'H100_80GB',
                    'gpu_count': 1,
                    'provider': 'AWS',
                    'location': 'us-west-2',
                    'cost_per_hour': 4.0,
                    'available_count': 1,
                    'total_count': 1,
                    'vcpus': 32,
                    'ram_gb': 128,
                    'disk_gb': 500,
                    'socket': 'socket1',
                    'availability': 'available'
                }
            ]
            
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
    
    @patch('prime_compute_manager.manager.parse_availability_table')
    def test_get_pod_status_existing(self, mock_parser):
        """Test getting status of existing pod."""
        # Create a mock pod
        with patch('prime_compute_manager.manager.subprocess.run') as mock_run:
            mock_result = Mock()
            mock_result.stdout = 'mock table output'
            mock_run.return_value = mock_result
            
            # Mock parser to return available resources
            mock_parser.return_value = [
                {
                    'id': 'test-config-1',
                    'gpu_type': 'H100_80GB',
                    'gpu_count': 1,
                    'provider': 'AWS',
                    'location': 'us-west-2',
                    'cost_per_hour': 4.0,
                    'available_count': 1,
                    'total_count': 1,
                    'vcpus': 32,
                    'ram_gb': 128,
                    'disk_gb': 500,
                    'socket': 'socket1',
                    'availability': 'available'
                }
            ]
            
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
    @patch('prime_compute_manager.manager.parse_pods_table')
    def test_list_pods_empty(self, mock_parser, mock_run):
        """Test listing pods when none exist."""
        mock_result = Mock()
        mock_result.stdout = 'empty table output'
        mock_run.return_value = mock_result
        
        # Mock parser to return empty list
        mock_parser.return_value = []
        
        pods = self.manager.list_pods()
        assert pods == []
    
    @patch('prime_compute_manager.manager.parse_pods_table')
    @patch('prime_compute_manager.manager.parse_availability_table')
    def test_list_pods_with_pods(self, mock_avail_parser, mock_pods_parser):
        """Test listing pods with existing pods."""
        # Create some mock pods
        with patch('prime_compute_manager.manager.subprocess.run') as mock_run:
            mock_result = Mock()
            mock_result.stdout = 'mock table output'
            mock_run.return_value = mock_result
            
            # Mock availability parser for pod creation
            mock_avail_parser.return_value = [
                {
                    'id': 'test-config-1',
                    'gpu_type': 'H100_80GB',
                    'gpu_count': 1,
                    'provider': 'AWS',
                    'location': 'us-west-2',
                    'cost_per_hour': 4.0,
                    'available_count': 1,
                    'total_count': 1,
                    'vcpus': 32,
                    'ram_gb': 128,
                    'disk_gb': 500,
                    'socket': 'socket1',
                    'availability': 'available'
                },
                {
                    'id': 'test-config-2',
                    'gpu_type': 'A100_80GB',
                    'gpu_count': 2,
                    'provider': 'AWS',
                    'location': 'us-west-2',
                    'cost_per_hour': 3.0,
                    'available_count': 2,
                    'total_count': 2,
                    'vcpus': 64,
                    'ram_gb': 256,
                    'disk_gb': 1000,
                    'socket': 'socket2',
                    'availability': 'available'
                }
            ]
            
            pod1 = self.manager.create_pod(gpu_type="H100_80GB", gpu_count=1, name="pod1")
            pod2 = self.manager.create_pod(gpu_type="A100_80GB", gpu_count=2, name="pod2")
            
            # Mock pods parser for list_pods
            mock_pods_parser.return_value = [
                {
                    'id': pod1.id,
                    'name': 'pod1',
                    'gpu_info': 'H100_80GB x 1',
                    'status': 'running',
                    'created': '2023-01-01'
                },
                {
                    'id': pod2.id,
                    'name': 'pod2',
                    'gpu_info': 'A100_80GB x 2',
                    'status': 'running',
                    'created': '2023-01-01'
                }
            ]
            
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
    
    @patch('prime_compute_manager.manager.parse_availability_table')
    def test_terminate_pod_success(self, mock_parser):
        """Test successful pod termination."""
        # Create a mock pod first
        with patch('prime_compute_manager.manager.subprocess.run') as mock_run:
            mock_result = Mock()
            mock_result.stdout = 'mock table output'
            mock_run.return_value = mock_result
            
            # Mock parser for pod creation
            mock_parser.return_value = [
                {
                    'id': 'test-config-1',
                    'gpu_type': 'H100_80GB',
                    'gpu_count': 1,
                    'provider': 'AWS',
                    'location': 'us-west-2',
                    'cost_per_hour': 4.0,
                    'available_count': 1,
                    'total_count': 1,
                    'vcpus': 32,
                    'ram_gb': 128,
                    'disk_gb': 500,
                    'socket': 'socket1',
                    'availability': 'available'
                }
            ]
            
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
    
    @patch('prime_compute_manager.manager.parse_availability_table')
    def test_ssh_to_pod_not_running(self, mock_parser):
        """Test SSH to pod that's not running."""
        # Create a mock pod that's not running
        with patch('prime_compute_manager.manager.subprocess.run') as mock_run:
            mock_result = Mock()
            mock_result.stdout = 'mock table output'
            mock_run.return_value = mock_result
            
            # Mock parser for pod creation
            mock_parser.return_value = [
                {
                    'id': 'test-config-1',
                    'gpu_type': 'H100_80GB',
                    'gpu_count': 1,
                    'provider': 'AWS',
                    'location': 'us-west-2',
                    'cost_per_hour': 4.0,
                    'available_count': 1,
                    'total_count': 1,
                    'vcpus': 32,
                    'ram_gb': 128,
                    'disk_gb': 500,
                    'socket': 'socket1',
                    'availability': 'available'
                }
            ]
            
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
    
    @patch('prime_compute_manager.manager.parse_availability_table')
    def test_ssh_to_pod_running(self, mock_parser):
        """Test SSH to running pod."""
        # Create and "start" a mock pod
        with patch('prime_compute_manager.manager.subprocess.run') as mock_run:
            mock_result = Mock()
            mock_result.stdout = 'mock table output'
            mock_run.return_value = mock_result
            
            # Mock parser for pod creation
            mock_parser.return_value = [
                {
                    'id': 'test-config-1',
                    'gpu_type': 'H100_80GB',
                    'gpu_count': 1,
                    'provider': 'AWS',
                    'location': 'us-west-2',
                    'cost_per_hour': 4.0,
                    'available_count': 1,
                    'total_count': 1,
                    'vcpus': 32,
                    'ram_gb': 128,
                    'disk_gb': 500,
                    'socket': 'socket1',
                    'availability': 'available'
                }
            ]
            
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