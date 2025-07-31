"""Parser for prime-cli table output."""

import re
from typing import List, Dict, Any, Optional


def parse_availability_table(output: str) -> List[Dict[str, Any]]:
    """Parse prime availability list table output with multi-line format.
    
    Args:
        output: Raw table output from prime availability list
        
    Returns:
        List of resource configurations
    """
    resources = []
    lines = output.strip().split('\n')
    
    # Find where the data section starts and ends
    data_start = -1
    data_end = len(lines)
    
    for i, line in enumerate(lines):
        if '┡' in line:  # Start of data section
            data_start = i + 1
        elif '└' in line:  # End of table
            data_end = i
            break
    
    if data_start == -1:
        return resources
    
    # Process data lines in groups (each resource spans multiple lines)
    i = data_start
    while i < data_end:
        line = lines[i]
        
        # Skip if not a table row
        if not line.startswith('│'):
            i += 1
            continue
        
        # Parse the line into columns
        parts = [p.strip() for p in line.split('│')[1:-1]]  # Remove empty first/last
        
        # Check if this is the start of a new resource (has an ID in first column)
        if len(parts) > 0 and parts[0] and not parts[0].isspace():
            # This is a new resource - collect all its lines
            resource_lines = [parts]
            
            # Look ahead for continuation lines
            j = i + 1
            while j < data_end and j < len(lines):
                next_line = lines[j]
                if not next_line.startswith('│'):
                    break
                    
                next_parts = [p.strip() for p in next_line.split('│')[1:-1]]
                
                # If the first column has content, it's a new resource
                if len(next_parts) > 0 and next_parts[0] and not next_parts[0].isspace():
                    break
                    
                # Otherwise it's a continuation
                resource_lines.append(next_parts)
                j += 1
            
            # Parse the multi-line resource
            resource = parse_multiline_resource(resource_lines)
            if resource:
                resources.append(resource)
            
            # Move to the next unprocessed line
            i = j
        else:
            i += 1
    
    return resources


def parse_multiline_resource(lines: List[List[str]]) -> Optional[Dict[str, Any]]:
    """Parse a single resource that spans multiple table lines."""
    if not lines or not lines[0]:
        return None
    
    # First line has most of the data
    main_line = lines[0]
    if len(main_line) < 12:  # Need all columns
        return None
    
    # Extract basic fields from first line
    resource_id = main_line[0]
    
    # GPU type is split across lines - collect all parts
    gpu_type_parts = []
    for line_parts in lines:
        if len(line_parts) > 1 and line_parts[1]:
            gpu_type_parts.append(line_parts[1])
    
    gpu_type_full = ' '.join(gpu_type_parts).replace('…', '').strip()
    
    # Map to our standard GPU types
    gpu_type = map_gpu_type(gpu_type_full)
    
    # Rest of the fields from the main line
    gpu_count = safe_int(main_line[2], 1)
    socket = main_line[3].replace('…', '') if len(main_line) > 3 else ''
    provider_raw = main_line[4].replace('…', '') if len(main_line) > 4 else ''
    location = main_line[5] if len(main_line) > 5 else ''
    status = main_line[6].replace('…', '') if len(main_line) > 6 else 'Unknown'
    price_raw = main_line[7].replace('…', '').replace('$', '') if len(main_line) > 7 else '0'
    security = main_line[8].replace('…', '') if len(main_line) > 8 else ''
    
    # Parse vCPUs (handle ranges like "2-8")
    vcpu_raw = main_line[9] if len(main_line) > 9 else '0'
    vcpus = parse_range_value(vcpu_raw)
    
    # Parse RAM (handle ranges like "8-64")
    ram_raw = main_line[10] if len(main_line) > 10 else '0'
    ram_gb = parse_range_value(ram_raw)
    
    # Parse disk
    disk_raw = main_line[11] if len(main_line) > 11 else '0'
    disk_gb = parse_range_value(disk_raw)
    
    # Map provider names
    provider = map_provider(provider_raw)
    
    # Parse price
    price_match = re.search(r'(\d+\.?\d*)', price_raw)
    cost_per_hour = float(price_match.group(1)) if price_match else 0.0
    
    # Determine availability
    is_available = 'ava' in status.lower() or 'med' in status.lower()
    
    return {
        'id': resource_id,
        'gpu_type': gpu_type,
        'gpu_count': gpu_count,
        'socket': socket,
        'provider': provider,
        'location': location,
        'availability': status,
        'cost_per_hour': cost_per_hour,
        'security': security,
        'vcpus': vcpus,
        'ram_gb': ram_gb,
        'disk_gb': disk_gb,
        'available_count': gpu_count if is_available else 0,
        'total_count': gpu_count
    }


def map_gpu_type(gpu_type_raw: str) -> str:
    """Map raw GPU type string to our standard enum values."""
    gpu_type_upper = gpu_type_raw.upper()
    
    # CPU types
    if 'CPU' in gpu_type_upper:
        return 'CPU'
    
    # NVIDIA H100
    elif 'H100' in gpu_type_upper or gpu_type_upper.startswith('H1'):
        if '80' in gpu_type_upper:
            return 'H100_80GB'
        elif '40' in gpu_type_upper:
            return 'H100_40GB'
        return 'H100_80GB'  # Default H100
    
    # NVIDIA A100
    elif 'A100' in gpu_type_upper or (gpu_type_upper.startswith('A1') and not gpu_type_upper.startswith('A10')):
        if '80' in gpu_type_upper:
            return 'A100_80GB'
        elif '40' in gpu_type_upper:
            return 'A100_40GB'
        return 'A100_80GB'  # Default A100
    
    # NVIDIA A6000
    elif 'A6000' in gpu_type_upper or (gpu_type_upper.startswith('A6') and '48' in gpu_type_upper):
        return 'RTX_A6000'
    
    # NVIDIA V100
    elif 'V100' in gpu_type_upper or gpu_type_upper.startswith('V1'):
        if '32' in gpu_type_upper:
            return 'V100_32GB'
        elif '16' in gpu_type_upper:
            return 'V100_16GB'
        # Default based on context clues
        return 'V100_16GB' if '16' in gpu_type_upper else 'V100_32GB'
    
    # NVIDIA L4
    elif gpu_type_upper.startswith('L4') or ' L4' in gpu_type_upper:
        return 'L4'
    
    # NVIDIA L40
    elif 'L40' in gpu_type_upper:
        if 'L40S' in gpu_type_upper:
            return 'L40S'
        return 'L40'
    
    # NVIDIA RTX 4090
    elif '4090' in gpu_type_upper or 'RTX 4090' in gpu_type_upper:
        return 'RTX_4090'
    
    # NVIDIA RTX 3090
    elif '3090' in gpu_type_upper or 'RTX 3090' in gpu_type_upper:
        return 'RTX_3090'
    
    # NVIDIA RTX 4080
    elif '4080' in gpu_type_upper:
        return 'RTX_4080'
    
    # NVIDIA RTX A5000
    elif 'A5000' in gpu_type_upper or 'RTX A5000' in gpu_type_upper:
        return 'RTX_A5000'
    
    # NVIDIA RTX A4000
    elif 'A4000' in gpu_type_upper or 'RTX A4000' in gpu_type_upper:
        return 'RTX_A4000'
    
    # NVIDIA T4
    elif gpu_type_upper.startswith('T4') or ' T4' in gpu_type_upper:
        return 'T4'
    
    # RTX with GB info (generic consumer card)
    elif gpu_type_upper.startswith('RT') and 'GB' in gpu_type_upper:
        # Try to extract the model number
        if '8GB' in gpu_type_upper:
            return 'UNKNOWN'  # Could be various RTX cards
    
    # Unknown
    else:
        return 'UNKNOWN'


def map_provider(provider_raw: str) -> str:
    """Map truncated provider names to full names."""
    provider_lower = provider_raw.lower()
    
    if 'dat' in provider_lower:
        return 'Datacrunch'
    elif 'mas' in provider_lower:
        return 'MassedCompute'
    elif 'hyp' in provider_lower:
        return 'Hyperstack'
    elif 'neb' in provider_lower:
        return 'Nebula'
    elif 'run' in provider_lower:
        return 'RunPod'
    elif 'lam' in provider_lower:
        return 'Lambda Labs'
    elif 'cru' in provider_lower:
        return 'cru'
    elif 'obl' in provider_lower:
        return 'obl'
    elif 'pri' in provider_lower:
        return 'pri'
    elif 'dc_' in provider_lower:
        return 'dc_'
    elif 'lat' in provider_lower:
        return 'lat'
    else:
        return provider_raw


def safe_int(value: str, default: int = 0) -> int:
    """Safely convert string to int."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def parse_range_value(value: str) -> int:
    """Parse a value that might be a range like '2-8' or '8-64'."""
    if '-' in value:
        parts = value.split('-')
        # Return the minimum value
        return safe_int(parts[0])
    else:
        return safe_int(value)


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