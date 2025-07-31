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
def resources():
    """Manage GPU resources."""
    pass


@main.group()  
def pods():
    """Manage compute pods."""
    pass


@resources.command("list")
@click.option("--gpu-type", type=click.Choice([gt.value for gt in GPUType.__members__.values()]), help="Filter by GPU type")
@click.option("--min-count", type=int, default=1, help="Minimum GPU count needed")
@click.option("--max-cost", type=float, help="Maximum cost per hour per GPU")
@click.option("--region", help="Preferred region")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def list_resources(gpu_type: Optional[str], min_count: int, max_cost: Optional[float], 
                  region: Optional[str], output_json: bool):
    """List available GPU resources."""
    try:
        manager = PrimeManager()
        resources = manager.find_gpus(
            gpu_type=gpu_type,
            min_count=min_count, 
            max_cost_per_hour=max_cost,
            regions=region
        )
        
        if output_json:
            click.echo(json.dumps([r.dict() for r in resources], indent=2, default=str))
            return
        
        if not resources:
            console.print("[red]No GPU resources found matching criteria[/red]")
            return
        
        table = Table(title="Available GPU Resources")
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
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.Abort()


@pods.command("create")
@click.option("--gpu-type", required=True, type=click.Choice([gt.value for gt in GPUType.__members__.values()]), 
              help="GPU type to request")
@click.option("--count", type=int, default=1, help="Number of GPUs")
@click.option("--name", help="Pod name")
@click.option("--region", help="Preferred region")
@click.option("--image", help="Container image")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def create_pod(gpu_type: str, count: int, name: Optional[str], region: Optional[str],
               image: Optional[str], output_json: bool):
    """Create a new compute pod."""
    try:
        manager = PrimeManager()
        pod = manager.create_pod(
            gpu_type=gpu_type,
            gpu_count=count,
            name=name,
            region=region,
            image=image
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
def ssh_pod(pod_id: str):
    """Get SSH connection command for a pod."""
    try:
        manager = PrimeManager()
        ssh_cmd = manager.ssh_to_pod(pod_id)
        
        console.print(f"[green]SSH connection:[/green] {ssh_cmd}")
        console.print(f"\n[dim]Copy and paste the command above to connect to your pod[/dim]")
        
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