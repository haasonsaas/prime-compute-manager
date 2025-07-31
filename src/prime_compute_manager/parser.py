"""Parser for prime-cli table output."""

import re
from typing import List, Dict, Any, Optional


def parse_availability_table(output: str) -> List[Dict[str, Any]]:
    """Parse prime availability list table output.
    
    Args:
        output: Raw table output from prime availability list
        
    Returns:
        List of resource configurations
    """
    resources = []
    
    # Split into lines and find the data rows
    lines = output.strip().split('\n')
    
    # Find lines that contain actual data (between the table borders)
    data_lines = []
    in_data_section = False
    
    for line in lines:
        # Start of data section (after header separator)
        if '┡━━━' in line:
            in_data_section = True
            continue
        # End of data section    
        if '└────' in line:
            break
        # Data row
        if in_data_section and line.startswith('│'):
            data_lines.append(line)
    
    # Parse each data row
    current_resource: Optional[Dict[str, Any]] = None
    for line in data_lines:
        # Split by │ and clean up
        parts = [part.strip() for part in line.split('│') if part.strip()]
        
        if len(parts) >= 8:  # At least basic columns
            # This is a new resource
            resource_id = parts[0]
            gpu_type_raw = parts[1].replace('…', '').replace('\n', ' ').strip()
            
            # Handle truncated GPU type - try to reconstruct
            if gpu_type_raw.startswith('H1'):
                gpu_type = 'H100_80GB'
            elif gpu_type_raw.startswith('A1'):
                gpu_type = 'A100_80GB'  
            elif gpu_type_raw.startswith('V1'):
                gpu_type = 'V100_32GB'
            else:
                gpu_type = gpu_type_raw
                
            gpu_count = int(parts[2]) if parts[2].isdigit() else 1
            socket = parts[3].replace('…', '') if len(parts) > 3 else ''
            provider_raw = parts[4].replace('…', '') if len(parts) > 4 else ''
            
            # Map truncated provider names
            provider = provider_raw
            if 'dat' in provider_raw.lower():
                provider = 'Datacrunch'
            elif 'mas' in provider_raw.lower():
                provider = 'MassedCompute'
            elif 'hyp' in provider_raw.lower():
                provider = 'Hyperstack'
            elif 'neb' in provider_raw.lower():
                provider = 'Nebula'
            elif 'run' in provider_raw.lower():
                provider = 'RunPod'
            elif 'lam' in provider_raw.lower():
                provider = 'Lambda Labs'
                
            location = parts[5] if len(parts) > 5 else ''
            availability = parts[6].replace('…', '') if len(parts) > 6 else 'Unknown'
            price_raw = parts[7].replace('…', '').replace('$', '') if len(parts) > 7 else '0'
            
            # Parse price - extract numeric value
            price_match = re.search(r'(\d+\.?\d*)', price_raw)
            cost_per_hour = float(price_match.group(1)) if price_match else 0.0
            
            vcpus = int(parts[9]) if len(parts) > 9 and parts[9].isdigit() else 0
            ram_gb = int(parts[10]) if len(parts) > 10 and parts[10].isdigit() else 0
            disk_gb_match = re.search(r'(\d+)', parts[11]) if len(parts) > 11 else None
            disk_gb = int(disk_gb_match.group(1)) if disk_gb_match else 0
            
            current_resource = {
                'id': resource_id,
                'gpu_type': gpu_type,
                'gpu_count': gpu_count,
                'socket': socket,
                'provider': provider,
                'location': location,
                'availability': availability,
                'cost_per_hour': cost_per_hour,
                'vcpus': vcpus,
                'ram_gb': ram_gb,
                'disk_gb': disk_gb,
                'available_count': 1 if availability.lower() in ['available', 'ava', 'medium', 'med'] else 0,
                'total_count': 1
            }
            resources.append(current_resource)
            
        elif current_resource and len(parts) >= 1:
            # This is a continuation line, update the current resource
            # Usually contains additional GPU info
            if parts[0] and not parts[0].isspace():
                current_resource['gpu_type'] += ' ' + parts[0].replace('…', '').strip()
    
    return resources


def parse_pods_table(output: str) -> List[Dict[str, Any]]:
    """Parse prime pods list table output.
    
    Args:
        output: Raw table output from prime pods list
        
    Returns:
        List of pods
    """
    pods = []
    
    # Split into lines and find the data rows
    lines = output.strip().split('\n')
    
    # Find lines that contain actual data
    data_lines = []
    in_data_section = False
    
    for line in lines:
        # Start of data section (after header separator)
        if '┡━━━' in line:
            in_data_section = True
            continue
        # End of data section    
        if '└────' in line:
            break
        # Data row
        if in_data_section and line.startswith('│'):
            data_lines.append(line)
    
    # Parse each data row
    for line in data_lines:
        # Split by │ and clean up
        parts = [part.strip() for part in line.split('│') if part.strip()]
        
        if len(parts) >= 5:  # Full row with all columns
            pod_id = parts[0]
            name = parts[1]
            gpu_info = parts[2]
            status = parts[3]
            created = parts[4]
            
            pod = {
                'id': pod_id,
                'name': name,
                'gpu_info': gpu_info,
                'status': status,
                'created': created
            }
            pods.append(pod)
    
    return pods


def parse_gpu_types_table(output: str) -> List[str]:
    """Parse prime availability gpu-types table output.
    
    Args:
        output: Raw table output from prime availability gpu-types
        
    Returns:
        List of GPU type strings
    """
    gpu_types = []
    
    # Split into lines and find the data rows
    lines = output.strip().split('\n')
    
    # Find lines that contain actual data
    in_data_section = False
    
    for line in lines:
        # Start of data section (after header separator)
        if '┡━━━' in line:
            in_data_section = True
            continue
        # End of data section    
        if '└─────' in line:
            break
        # Data row
        if in_data_section and line.startswith('│'):
            # Split by │ and clean up
            parts = [part.strip() for part in line.split('│') if part.strip()]
            if parts:
                gpu_types.append(parts[0])
    
    return gpu_types