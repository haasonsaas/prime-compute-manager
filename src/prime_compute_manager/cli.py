"""Command line interface for Prime Compute Manager."""

import click
import json
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from typing import Optional

from .manager import PrimeManager
from .models import GPUType

console = Console()


@click.group()
@click.version_option()
def main():
    """Prime Compute Manager - GPU resource management with PrimeIntellect integration."""
    pass




@main.group()
@click.option('--no-api', is_flag=True, help='Disable direct API access and use CLI parsing instead')
@click.pass_context
def resources(ctx, no_api):
    """Manage GPU resources."""
    ctx.ensure_object(dict)
    ctx.obj['use_api'] = not no_api  # Default is to use API


@main.group()  
def pods():
    """Manage compute pods."""
    pass


@resources.command("list")
@click.option("--gpu-type", type=click.Choice([gt.value for gt in GPUType.__members__.values()]), help="Filter by GPU type")
@click.option("--min-count", type=int, default=1, help="Minimum GPU count needed")
@click.option("--max-cost", type=float, help="Maximum cost per hour per GPU")
@click.option("--min-cost", type=float, help="Minimum cost per hour per GPU")
@click.option("--region", help="Preferred region (comma-separated)")
@click.option("--provider", help="Filter by provider (e.g., runpod, lambda, aws)")
@click.option("--min-availability", type=int, help="Minimum available GPU count")
@click.option("--sort-by", type=click.Choice(["cost", "availability", "utilization", "gpu_type", "provider"]), 
              default="cost", help="Sort results by field")
@click.option("--sort-desc", is_flag=True, help="Sort in descending order")
@click.option("--limit", type=int, default=50, help="Maximum number of results to show")
@click.option("--include-free", is_flag=True, help="Include $0.00 entries (likely unavailable)")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
@click.pass_context
def list_resources(ctx, gpu_type: Optional[str], min_count: int, max_cost: Optional[float], 
                  min_cost: Optional[float], region: Optional[str], provider: Optional[str],
                  min_availability: Optional[int], sort_by: str, sort_desc: bool, limit: int,
                  include_free: bool, output_json: bool):
    """List available GPU resources."""
    try:
        use_api = ctx.obj.get('use_api', True)  # Default to True
        manager = PrimeManager(use_api=use_api)
        resources = manager.find_gpus(
            gpu_type=gpu_type,
            min_count=min_count, 
            max_cost_per_hour=max_cost,
            regions=region,
            provider=provider,
            include_free=include_free
        )
        
        # Apply additional local filters
        if min_cost is not None:
            resources = [r for r in resources if r.cost_per_hour >= min_cost]
        
        if min_availability is not None:
            resources = [r for r in resources if r.available_count >= min_availability]
        
        # Sort resources
        reverse = sort_desc
        if sort_by == "cost":
            resources.sort(key=lambda r: r.cost_per_hour, reverse=reverse)
        elif sort_by == "availability":
            resources.sort(key=lambda r: r.available_count, reverse=reverse)
        elif sort_by == "utilization":
            resources.sort(key=lambda r: r.utilization, reverse=reverse)
        elif sort_by == "gpu_type":
            resources.sort(key=lambda r: r.gpu_type.value, reverse=reverse)
        elif sort_by == "provider":
            resources.sort(key=lambda r: r.provider, reverse=reverse)
        
        # Limit results
        if limit > 0:
            resources = resources[:limit]
        
        if output_json:
            click.echo(json.dumps([r.dict() for r in resources], indent=2, default=str))
            return
        
        if not resources:
            console.print("[red]No GPU resources found matching criteria[/red]")
            return
        
        # Check if we're using degraded mode and add sorting info
        title = "Available GPU Resources"
        if not manager.use_api:
            title += " [yellow](CLI Parsing Mode - Limited Quality)[/yellow]"
        
        # Add sorting and filtering info to title
        sort_arrow = "↓" if sort_desc else "↑"
        title += f" [dim](sorted by {sort_by} {sort_arrow}"
        if limit < len(resources) + len([r for r in resources if not include_free and r.cost_per_hour <= 0]):
            title += f", showing top {limit}"
        title += ")[/dim]"
        
        table = Table(title=title)
        table.add_column("GPU Type", style="cyan")
        table.add_column("Available", justify="right")
        table.add_column("Total", justify="right") 
        table.add_column("Utilization", justify="right")
        table.add_column("Cost/Hour", justify="right", style="green")
        table.add_column("Provider", style="blue")
        table.add_column("Region", style="magenta")
        
        for resource in resources:
            table.add_row(
                resource.gpu_type.value,
                str(resource.available_count),
                str(resource.total_count),
                f"{resource.utilization:.1f}%",
                f"${resource.cost_per_hour:.2f}",
                resource.provider,
                resource.region
            )
        
        console.print(table)
        
        # Show warning if there are unknown GPU types
        if not manager.use_api and any(r.gpu_type.value == "UNKNOWN" for r in resources):
            console.print("\n[yellow]⚠️  Note: Some GPU types shown as 'UNKNOWN' due to truncated CLI output.[/yellow]")
            
            # Check if we can find prime in venv to give better instructions
            import os
            import sys
            venv_prime = None
            if hasattr(sys, 'prefix') and sys.prefix:
                venv_prime_path = os.path.join(sys.prefix, 'bin', 'prime')
                if os.path.exists(venv_prime_path):
                    venv_prime = venv_prime_path
            
            if venv_prime:
                console.print(f"[yellow]   For accurate GPU identification, authenticate with: [bold]{venv_prime} login[/bold][/yellow]")
                console.print("[yellow]   Or simply run: [bold]./prime-login.sh[/bold][/yellow]")
            else:
                console.print("[yellow]   For accurate GPU identification, authenticate with: [bold]prime login[/bold][/yellow]")
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.Abort()


@resources.command("compare")
@click.option("--gpu-types", required=True, help="Comma-separated list of GPU types to compare")
@click.option("--min-count", type=int, default=1, help="Minimum GPU count needed")
@click.option("--max-cost", type=float, help="Maximum cost per hour per GPU")
@click.option("--region", help="Preferred region")
@click.option("--provider", help="Filter by provider")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
@click.pass_context
def compare_resources(ctx, gpu_types: str, min_count: int, max_cost: Optional[float],
                     region: Optional[str], provider: Optional[str], output_json: bool):
    """Compare different GPU types side by side."""
    try:
        use_api = ctx.obj.get('use_api', True)
        manager = PrimeManager(use_api=use_api)
        
        # Parse GPU types
        gpu_type_list = [gt.strip() for gt in gpu_types.split(',')]
        
        # Validate GPU types
        valid_gpu_types = [gt.value for gt in GPUType.__members__.values()]
        for gpu_type in gpu_type_list:
            if gpu_type not in valid_gpu_types:
                console.print(f"[red]Invalid GPU type: {gpu_type}[/red]")
                console.print(f"[yellow]Valid types: {', '.join(valid_gpu_types)}[/yellow]")
                return
        
        # Get resources for each GPU type
        comparison_data = {}
        for gpu_type in gpu_type_list:
            resources = manager.find_gpus(
                gpu_type=gpu_type,
                min_count=min_count,
                max_cost_per_hour=max_cost,
                regions=region,
                provider=provider,
                include_free=False
            )
            
            if resources:
                # Get best (cheapest) option
                best_resource = min(resources, key=lambda r: r.cost_per_hour)
                comparison_data[gpu_type] = {
                    "best_resource": best_resource,
                    "total_options": len(resources),
                    "price_range": {
                        "min": min(r.cost_per_hour for r in resources),
                        "max": max(r.cost_per_hour for r in resources)
                    },
                    "total_availability": sum(r.available_count for r in resources)
                }
            else:
                comparison_data[gpu_type] = None
        
        if output_json:
            # Convert to JSON-serializable format
            json_data = {}
            for gpu_type, data in comparison_data.items():
                if data:
                    json_data[gpu_type] = {
                        "best_option": data["best_resource"].dict(),
                        "total_options": data["total_options"],
                        "price_range": data["price_range"],
                        "total_availability": data["total_availability"]
                    }
                else:
                    json_data[gpu_type] = None
            
            click.echo(json.dumps(json_data, indent=2, default=str))
            return
        
        # Create comparison table
        table = Table(title="GPU Type Comparison")
        table.add_column("GPU Type", style="cyan")
        table.add_column("Best Price", justify="right", style="green")
        table.add_column("Price Range", justify="right")
        table.add_column("Options", justify="right")
        table.add_column("Total Available", justify="right")
        table.add_column("Best Provider", style="blue")
        table.add_column("Best Region", style="magenta")
        
        for gpu_type in gpu_type_list:
            data = comparison_data.get(gpu_type)
            if data:
                best = data["best_resource"]
                price_range = data["price_range"]
                table.add_row(
                    gpu_type,
                    f"${best.cost_per_hour:.2f}/hr",
                    f"${price_range['min']:.2f} - ${price_range['max']:.2f}",
                    str(data["total_options"]),
                    str(data["total_availability"]),
                    best.provider,
                    best.region
                )
            else:
                table.add_row(
                    gpu_type,
                    "[red]N/A[/red]",
                    "[red]N/A[/red]",
                    "0",
                    "0",
                    "[red]N/A[/red]",
                    "[red]N/A[/red]"
                )
        
        console.print(table)
        
        # Show cost estimation for common durations
        console.print("\n[bold]Cost Estimation (1 GPU):[/bold]")
        durations = [("1 hour", 1), ("8 hours", 8), ("1 day", 24), ("1 week", 168), ("1 month", 720)]
        
        cost_table = Table()
        cost_table.add_column("Duration")
        for gpu_type in gpu_type_list:
            cost_table.add_column(gpu_type, justify="right", style="green")
        
        for duration_name, hours in durations:
            row = [duration_name]
            for gpu_type in gpu_type_list:
                data = comparison_data.get(gpu_type)
                if data:
                    cost = data["best_resource"].cost_per_hour * hours
                    row.append(f"${cost:.2f}")
                else:
                    row.append("[red]N/A[/red]")
            cost_table.add_row(*row)
        
        console.print(cost_table)
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.Abort()


@pods.command("create")
@click.option("--gpu-type", required=True, type=click.Choice([gt.value for gt in GPUType.__members__.values()]), 
              help="GPU type to request")
@click.option("--count", type=int, default=1, help="Number of GPUs")
@click.option("--name", help="Pod name")
@click.option("--region", help="Preferred region")
@click.option("--image", default="pytorch/pytorch:2.0.1-cuda11.7-cudnn8-devel", help="Container image")
@click.option("--disk-size", type=int, default=50, help="Disk size in GB")
@click.option("--vcpus", type=int, help="Number of vCPUs")
@click.option("--memory", type=int, help="Memory in GB")
@click.option("--env", multiple=True, help="Environment variables (KEY=value)")
@click.option("--dry-run", is_flag=True, help="Show what would be created without actually creating")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def create_pod(gpu_type: str, count: int, name: Optional[str], region: Optional[str],
               image: str, disk_size: int, vcpus: Optional[int], memory: Optional[int],
               env: tuple, dry_run: bool, output_json: bool):
    """Create a new compute pod."""
    try:
        manager = PrimeManager()
        
        # Parse environment variables
        env_dict = {}
        for env_var in env:
            if "=" in env_var:
                key, value = env_var.split("=", 1)
                env_dict[key] = value
        
        if dry_run:
            # Find matching resources and show what would be created
            resources = manager.find_gpus(
                gpu_type=gpu_type,
                min_count=count,
                regions=region
            )
            
            if not resources:
                console.print(f"[red]No available {gpu_type} resources found with {count} GPUs[/red]")
                return
                
            selected = resources[0]  # Would use cheapest available
            
            if output_json:
                dry_run_info = {
                    "action": "create_pod",
                    "dry_run": True,
                    "selected_resource": selected.dict(),
                    "estimated_cost_per_hour": selected.cost_per_hour,
                    "pod_config": {
                        "name": name or f"pod-{gpu_type.lower()}-{count}gpu",
                        "gpu_type": gpu_type,
                        "gpu_count": count,
                        "region": region,
                        "image": image,
                        "disk_size": disk_size,
                        "vcpus": vcpus,
                        "memory": memory,
                        "env": env_dict
                    }
                }
                click.echo(json.dumps(dry_run_info, indent=2, default=str))
                return
            
            env_display = "\n".join([f"    {k}={v}" for k, v in env_dict.items()]) if env_dict else "    (none)"
            
            panel = Panel.fit(
                f"[yellow]DRY RUN - Pod would be created with:[/yellow]\n\n"
                f"[bold]Selected Resource:[/bold]\n"
                f"  GPU Type: {selected.gpu_type.value}\n"
                f"  Provider: {selected.provider}\n"
                f"  Region: {selected.region}\n"
                f"  Available: {selected.available_count}/{selected.total_count}\n"
                f"  Cost: ${selected.cost_per_hour:.2f}/hour\n\n"
                f"[bold]Pod Configuration:[/bold]\n"
                f"  Name: {name or f'pod-{gpu_type.lower()}-{count}gpu'}\n"
                f"  GPU Count: {count}\n"
                f"  Image: {image}\n"
                f"  Disk Size: {disk_size} GB\n"
                + (f"  vCPUs: {vcpus}\n" if vcpus else "")
                + (f"  Memory: {memory} GB\n" if memory else "")
                + f"  Environment:\n{env_display}\n\n"
                f"[bold green]Estimated Cost: ${selected.cost_per_hour:.2f}/hour[/bold green]\n"
                f"[dim]Use without --dry-run to actually create this pod[/dim]",
                title="Pod Creation Preview",
                border_style="yellow"
            )
            console.print(panel)
            return
        
        # Prepare kwargs for pod creation
        pod_kwargs = {
            "gpu_count": count,
            "disk_size": disk_size,
            "image": image
        }
        if vcpus:
            pod_kwargs["vcpus"] = vcpus
        if memory:
            pod_kwargs["memory"] = memory
        if env_dict:
            pod_kwargs["env"] = env_dict
        
        pod = manager.create_pod(
            gpu_type=gpu_type,
            gpu_count=count,
            name=name,
            regions=region,
            **pod_kwargs
        )
        
        if output_json:
            click.echo(json.dumps(pod.dict(), indent=2, default=str))
            return
        
        panel = Panel.fit(
            f"[green]Pod created successfully![/green]\n\n"
            f"[bold]ID:[/bold] {pod.id}\n"
            f"[bold]Name:[/bold] {pod.name}\n"
            f"[bold]Status:[/bold] {pod.status.value}\n"
            f"[bold]GPU Type:[/bold] {pod.gpu_type.value}\n"
            f"[bold]GPU Count:[/bold] {pod.gpu_count}\n"
            f"[bold]Cost/Hour:[/bold] ${pod.cost_per_hour:.2f}\n"
            f"[bold]Provider:[/bold] {pod.provider}\n"
            f"[bold]Region:[/bold] {pod.region}",
            title="Pod Created"
        )
        console.print(panel)
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.Abort()


@pods.command("list")
@click.option("--all", is_flag=True, help="Show all pods including stopped")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def list_pods(all: bool, output_json: bool):
    """List compute pods."""
    try:
        manager = PrimeManager()
        pods = manager.list_pods(active_only=not all)
        
        if output_json:
            click.echo(json.dumps([p.dict() for p in pods], indent=2, default=str))
            return
        
        if not pods:
            console.print("[yellow]No pods found[/yellow]")
            return
        
        table = Table(title="Compute Pods")
        table.add_column("ID", style="cyan")
        table.add_column("Name")
        table.add_column("Status", style="green")
        table.add_column("GPU Type", style="blue")
        table.add_column("Count", justify="right")
        table.add_column("Runtime", justify="right")
        table.add_column("Cost", justify="right", style="red")
        table.add_column("Provider")
        
        for pod in pods:
            status_color = {
                "running": "green",
                "creating": "yellow", 
                "stopped": "red",
                "failed": "red"
            }.get(pod.status.value, "white")
            
            table.add_row(
                pod.id[:12] + "...",
                pod.name,
                f"[{status_color}]{pod.status.value}[/{status_color}]",
                pod.gpu_type.value,
                str(pod.gpu_count),
                f"{pod.runtime_hours:.1f}h",
                f"${pod.total_cost:.2f}",
                pod.provider
            )
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.Abort()


@pods.command("status")
@click.argument("pod_id")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def pod_status(pod_id: str, output_json: bool):
    """Get status of a specific pod."""
    try:
        manager = PrimeManager()
        pod = manager.get_pod_status(pod_id)
        
        if output_json:
            click.echo(json.dumps(pod.dict(), indent=2, default=str))
            return
        
        status_color = {
            "running": "green",
            "creating": "yellow",
            "stopped": "red", 
            "failed": "red"
        }.get(pod.status.value, "white")
        
        panel = Panel.fit(
            f"[bold]ID:[/bold] {pod.id}\n"
            f"[bold]Name:[/bold] {pod.name}\n"
            f"[bold]Status:[/bold] [{status_color}]{pod.status.value}[/{status_color}]\n"
            f"[bold]GPU Type:[/bold] {pod.gpu_type.value}\n"
            f"[bold]GPU Count:[/bold] {pod.gpu_count}\n"
            f"[bold]Runtime:[/bold] {pod.runtime_hours:.1f} hours\n"
            f"[bold]Total Cost:[/bold] ${pod.total_cost:.2f}\n"
            f"[bold]Provider:[/bold] {pod.provider}\n"
            f"[bold]Region:[/bold] {pod.region}\n"
            + (f"[bold]SSH:[/bold] {pod.ssh_connection}" if pod.ssh_connection else ""),
            title=f"Pod Status: {pod.name}"
        )
        console.print(panel)
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.Abort()


@pods.command("ssh")
@click.argument("pod_id")
@click.option("--interactive", "-i", is_flag=True, help="Launch interactive SSH session")
def ssh_pod(pod_id: str, interactive: bool):
    """SSH to a pod or get SSH connection command."""
    try:
        manager = PrimeManager()
        
        if interactive:
            # Launch interactive SSH session
            result = manager.ssh_to_pod(pod_id, interactive=True)
            console.print(f"[green]{result}[/green]")
        else:
            # Get SSH connection command
            ssh_cmd = manager.ssh_to_pod(pod_id, interactive=False)
            console.print(f"[green]SSH connection:[/green] {ssh_cmd}")
            console.print(f"\n[dim]Copy and paste the command above to connect to your pod[/dim]")
            console.print(f"[dim]Or use --interactive flag to launch SSH session directly[/dim]")
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.Abort()


@pods.command("logs")
@click.argument("pod_id")
@click.option("--lines", "-n", type=int, default=100, help="Number of log lines to retrieve")
@click.option("--follow", "-f", is_flag=True, help="Follow log output (if supported)")
def pod_logs(pod_id: str, lines: int, follow: bool):
    """Get logs from a pod."""
    try:
        manager = PrimeManager()
        
        if follow:
            console.print("[yellow]Note: Follow mode may not be supported by all providers[/yellow]")
        
        logs = manager.get_pod_logs(pod_id, lines=lines)
        
        if logs.strip():
            console.print(f"[green]Pod {pod_id} logs (last {lines} lines):[/green]\n")
            console.print(logs)
        else:
            console.print(f"[yellow]No logs available for pod {pod_id}[/yellow]")
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.Abort()


@pods.command("terminate")
@click.argument("pod_id")
@click.option("--yes", is_flag=True, help="Skip confirmation")
def terminate_pod(pod_id: str, yes: bool):
    """Terminate a compute pod."""
    try:
        manager = PrimeManager()
        
        if not yes:
            pod = manager.get_pod_status(pod_id)
            if not click.confirm(f"Are you sure you want to terminate pod '{pod.name}' ({pod_id})?"):
                return
        
        success = manager.terminate_pod(pod_id)
        
        if success:
            console.print(f"[green]Pod {pod_id} terminated successfully[/green]")
        else:
            console.print(f"[red]Failed to terminate pod {pod_id}[/red]")
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.Abort()


if __name__ == "__main__":
    main()