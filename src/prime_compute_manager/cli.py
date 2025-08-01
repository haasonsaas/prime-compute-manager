"""Command line interface for Prime Compute Manager."""

import click
import json
import os
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from typing import Optional

from .manager import PrimeManager
from .models import GPUType
from .config import ConfigManager, PodConfig
from .ssh_manager import SSHManager

console = Console()


@click.group()
@click.version_option()
def main():
    """Prime Compute Manager - GPU resource management with PrimeIntellect integration."""
    pass


@main.command()
def status():
    """Show PCM status and configuration summary."""
    try:
        config_manager = ConfigManager()

        # Get active pod info
        active_pod = config_manager.get_active_pod()
        all_pods = config_manager.list_pods()

        status_text = "[bold]Prime Compute Manager Status[/bold]\n\n"

        # Configuration info
        status_text += (
            f"[bold]Configuration:[/bold] {config_manager.get_config_path()}\n"
        )
        status_text += f"[bold]Pods Configured:[/bold] {len(all_pods)}\n\n"

        # Active pod info
        if active_pod:
            status_text += (
                f"[bold]Active Pod:[/bold] [green]{active_pod.name}[/green]\n"
            )
            status_text += f"  SSH: {active_pod.ssh_command}\n"
            status_text += f"  Provider: {active_pod.provider}\n"
            status_text += f"  Region: {active_pod.region}\n"
            status_text += f"  GPUs: {active_pod.gpu_count} x {active_pod.gpu_type}\n"

            # Test connectivity
            try:
                ssh_manager = SSHManager(config_manager)
                pod_status = ssh_manager.check_pod_status(active_pod)
                if pod_status.get("reachable"):
                    status_text += f"  Status: [green]✓ Reachable[/green]\n"
                    status_text += (
                        f"  Hostname: {pod_status.get('hostname', 'unknown')}\n"
                    )
                else:
                    status_text += f"  Status: [red]✗ Unreachable[/red]\n"
            except:
                status_text += f"  Status: [yellow]? Unknown[/yellow]\n"
        else:
            status_text += "[yellow]No active pod configured[/yellow]\n"

        status_text += "\n[bold]Quick Commands:[/bold]\n"
        status_text += "  [bold]pcm pod setup <name> <ssh>[/bold]     Setup new pod\n"
        status_text += (
            "  [bold]pcm pod list[/bold]                   List configured pods\n"
        )
        status_text += (
            "  [bold]pcm pod shell[/bold]                  SSH to active pod\n"
        )
        status_text += (
            "  [bold]pcm resources list[/bold]             List GPU resources\n"
        )
        status_text += "  [bold]pcm pods create[/bold]                Create new pod\n"

        panel = Panel.fit(status_text.strip(), title="PCM Status", border_style="blue")
        console.print(panel)

        # Show all configured pods if more than just active
        if len(all_pods) > 1:
            console.print("\n[bold]All Configured Pods:[/bold]")
            for pod in all_pods:
                status_icon = "●" if active_pod and pod.name == active_pod.name else "○"
                console.print(f"  {status_icon} {pod.name} ({pod.provider})")

    except Exception as e:
        console.print(f"[red]Error getting status: {e}[/red]")
        raise click.Abort()


@main.group()
@click.option(
    "--no-api",
    is_flag=True,
    help="Disable direct API access and use CLI parsing instead",
)
@click.pass_context
def resources(ctx, no_api):
    """Manage GPU resources."""
    ctx.ensure_object(dict)
    ctx.obj["use_api"] = not no_api  # Default is to use API


@main.group()
def pods():
    """Manage compute pods."""
    pass


@main.group()
def pod():
    """Pod configuration management (similar to badlogic/pi)."""
    pass


@resources.command("list")
@click.option(
    "--gpu-type",
    type=click.Choice([gt.value for gt in GPUType.__members__.values()]),
    help="Filter by GPU type",
)
@click.option("--min-count", type=int, default=1, help="Minimum GPU count needed")
@click.option("--max-cost", type=float, help="Maximum cost per hour per GPU")
@click.option("--min-cost", type=float, help="Minimum cost per hour per GPU")
@click.option("--region", help="Preferred region (comma-separated)")
@click.option("--provider", help="Filter by provider (e.g., runpod, lambda, aws)")
@click.option("--min-availability", type=int, help="Minimum available GPU count")
@click.option(
    "--sort-by",
    type=click.Choice(["cost", "availability", "utilization", "gpu_type", "provider"]),
    default="cost",
    help="Sort results by field",
)
@click.option("--sort-desc", is_flag=True, help="Sort in descending order")
@click.option("--limit", type=int, default=50, help="Maximum number of results to show")
@click.option(
    "--include-free", is_flag=True, help="Include $0.00 entries (likely unavailable)"
)
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
@click.option("--show-active-pod", is_flag=True, help="Show active pod information")
@click.pass_context
def list_resources(
    ctx,
    gpu_type: Optional[str],
    min_count: int,
    max_cost: Optional[float],
    min_cost: Optional[float],
    region: Optional[str],
    provider: Optional[str],
    min_availability: Optional[int],
    sort_by: str,
    sort_desc: bool,
    limit: int,
    include_free: bool,
    output_json: bool,
    show_active_pod: bool,
):
    """List available GPU resources."""
    try:
        use_api = ctx.obj.get("use_api", True)  # Default to True
        manager = PrimeManager(use_api=use_api)
        resources = manager.find_gpus(
            gpu_type=gpu_type,
            min_count=min_count,
            max_cost_per_hour=max_cost,
            regions=region,
            provider=provider,
            include_free=include_free,
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
        if limit < len(resources) + len(
            [r for r in resources if not include_free and r.cost_per_hour <= 0]
        ):
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
                resource.region,
            )

        console.print(table)

        # Show active pod information if requested
        if show_active_pod:
            try:
                config_manager = ConfigManager()
                active_pod = config_manager.get_active_pod()
                if active_pod:
                    console.print(
                        f"\n[bold]Active Pod:[/bold] [cyan]{active_pod.name}[/cyan]"
                    )
                    console.print(f"[dim]SSH: {active_pod.ssh_command}[/dim]")
                    console.print(
                        f"[dim]Provider: {active_pod.provider}, Region: {active_pod.region}[/dim]"
                    )
                else:
                    console.print(
                        "\n[yellow]No active pod configured. Use 'pcm pod setup' to configure one.[/yellow]"
                    )
            except Exception as e:
                console.print(
                    f"\n[yellow]Could not load pod configuration: {e}[/yellow]"
                )

        # Show warning if there are unknown GPU types
        if not manager.use_api and any(
            r.gpu_type.value == "UNKNOWN" for r in resources
        ):
            console.print(
                "\n[yellow]⚠️  Note: Some GPU types shown as 'UNKNOWN' due to truncated CLI output.[/yellow]"
            )

            # Check if we can find prime in venv to give better instructions
            import os
            import sys

            venv_prime = None
            if hasattr(sys, "prefix") and sys.prefix:
                venv_prime_path = os.path.join(sys.prefix, "bin", "prime")
                if os.path.exists(venv_prime_path):
                    venv_prime = venv_prime_path

            if venv_prime:
                console.print(
                    f"[yellow]   For accurate GPU identification, authenticate with: [bold]{venv_prime} login[/bold][/yellow]"
                )
                console.print(
                    "[yellow]   Or simply run: [bold]./prime-login.sh[/bold][/yellow]"
                )
            else:
                console.print(
                    "[yellow]   For accurate GPU identification, authenticate with: [bold]prime login[/bold][/yellow]"
                )

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.Abort()


@resources.command("compare")
@click.option(
    "--gpu-types", required=True, help="Comma-separated list of GPU types to compare"
)
@click.option("--min-count", type=int, default=1, help="Minimum GPU count needed")
@click.option("--max-cost", type=float, help="Maximum cost per hour per GPU")
@click.option("--region", help="Preferred region")
@click.option("--provider", help="Filter by provider")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
@click.pass_context
def compare_resources(
    ctx,
    gpu_types: str,
    min_count: int,
    max_cost: Optional[float],
    region: Optional[str],
    provider: Optional[str],
    output_json: bool,
):
    """Compare different GPU types side by side."""
    try:
        use_api = ctx.obj.get("use_api", True)
        manager = PrimeManager(use_api=use_api)

        # Parse GPU types
        gpu_type_list = [gt.strip() for gt in gpu_types.split(",")]

        # Validate GPU types
        valid_gpu_types = [gt.value for gt in GPUType.__members__.values()]
        for gpu_type in gpu_type_list:
            if gpu_type not in valid_gpu_types:
                console.print(f"[red]Invalid GPU type: {gpu_type}[/red]")
                console.print(
                    f"[yellow]Valid types: {', '.join(valid_gpu_types)}[/yellow]"
                )
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
                include_free=False,
            )

            if resources:
                # Get best (cheapest) option
                best_resource = min(resources, key=lambda r: r.cost_per_hour)
                comparison_data[gpu_type] = {
                    "best_resource": best_resource,
                    "total_options": len(resources),
                    "price_range": {
                        "min": min(r.cost_per_hour for r in resources),
                        "max": max(r.cost_per_hour for r in resources),
                    },
                    "total_availability": sum(r.available_count for r in resources),
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
                        "total_availability": data["total_availability"],
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
                    best.region,
                )
            else:
                table.add_row(
                    gpu_type,
                    "[red]N/A[/red]",
                    "[red]N/A[/red]",
                    "0",
                    "0",
                    "[red]N/A[/red]",
                    "[red]N/A[/red]",
                )

        console.print(table)

        # Show cost estimation for common durations
        console.print("\n[bold]Cost Estimation (1 GPU):[/bold]")
        durations = [
            ("1 hour", 1),
            ("8 hours", 8),
            ("1 day", 24),
            ("1 week", 168),
            ("1 month", 720),
        ]

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
@click.option(
    "--gpu-type",
    required=True,
    type=click.Choice([gt.value for gt in GPUType.__members__.values()]),
    help="GPU type to request",
)
@click.option("--count", type=int, default=1, help="Number of GPUs")
@click.option("--name", help="Pod name")
@click.option("--region", help="Preferred region")
@click.option(
    "--image",
    default="pytorch/pytorch:2.0.1-cuda11.7-cudnn8-devel",
    help="Container image",
)
@click.option("--disk-size", type=int, default=50, help="Disk size in GB")
@click.option("--vcpus", type=int, help="Number of vCPUs")
@click.option("--memory", type=int, help="Memory in GB")
@click.option("--env", multiple=True, help="Environment variables (KEY=value)")
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be created without actually creating",
)
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
@click.option(
    "--auto-configure",
    is_flag=True,
    help="Automatically add created pod to configuration",
)
def create_pod(
    gpu_type: str,
    count: int,
    name: Optional[str],
    region: Optional[str],
    image: str,
    disk_size: int,
    vcpus: Optional[int],
    memory: Optional[int],
    env: tuple,
    dry_run: bool,
    output_json: bool,
    auto_configure: bool,
):
    """Create a new compute pod."""
    try:
        manager = PrimeManager()
        config_manager = ConfigManager() if auto_configure else None

        # Parse environment variables
        env_dict = {}
        for env_var in env:
            if "=" in env_var:
                key, value = env_var.split("=", 1)
                env_dict[key] = value

        if dry_run:
            # Find matching resources and show what would be created
            resources = manager.find_gpus(
                gpu_type=gpu_type, min_count=count, regions=region
            )

            if not resources:
                console.print(
                    f"[red]No available {gpu_type} resources found with {count} GPUs[/red]"
                )
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
                        "env": env_dict,
                    },
                }
                click.echo(json.dumps(dry_run_info, indent=2, default=str))
                return

            env_display = (
                "\n".join([f"    {k}={v}" for k, v in env_dict.items()])
                if env_dict
                else "    (none)"
            )

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
                border_style="yellow",
            )
            console.print(panel)
            return

        # Prepare kwargs for pod creation
        pod_kwargs = {"gpu_count": count, "disk_size": disk_size, "image": image}
        if vcpus:
            pod_kwargs["vcpus"] = vcpus
        if memory:
            pod_kwargs["memory"] = memory
        if env_dict:
            pod_kwargs["env"] = env_dict

        pod = manager.create_pod(
            gpu_type=gpu_type, gpu_count=count, name=name, regions=region, **pod_kwargs
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
            title="Pod Created",
        )
        console.print(panel)

        # Auto-configure pod if requested
        if auto_configure and config_manager:
            try:
                # Wait a moment for pod to get SSH info
                import time

                console.print("\n[dim]Waiting for pod SSH information...[/dim]")
                time.sleep(5)

                # Try to get updated pod info with SSH
                updated_pod = manager.get_pod_status(pod.id)
                if updated_pod.ssh_connection:
                    config_manager.add_pod(
                        name=pod.name,
                        ssh_command=updated_pod.ssh_connection,
                        provider=pod.provider,
                        region=pod.region,
                        gpu_type=pod.gpu_type.value,
                        gpu_count=pod.gpu_count,
                        cost_per_hour=pod.cost_per_hour,
                        pod_id=pod.id,
                        status=pod.status.value,
                    )
                    console.print(
                        f"[green]✓ Pod '{pod.name}' added to configuration[/green]"
                    )
                    console.print(
                        f"[dim]Use 'pcm pod switch {pod.name}' to make it active[/dim]"
                    )
                else:
                    console.print(
                        "[yellow]⚠ Pod created but SSH info not yet available for auto-configuration[/yellow]"
                    )
                    console.print(
                        f"[dim]You can add it later with: pcm pod setup {pod.name} <ssh_command>[/dim]"
                    )
            except Exception as e:
                console.print(
                    f"[yellow]⚠ Pod created but auto-configuration failed: {e}[/yellow]"
                )

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
                "failed": "red",
            }.get(pod.status.value, "white")

            table.add_row(
                pod.id[:12] + "...",
                pod.name,
                f"[{status_color}]{pod.status.value}[/{status_color}]",
                pod.gpu_type.value,
                str(pod.gpu_count),
                f"{pod.runtime_hours:.1f}h",
                f"${pod.total_cost:.2f}",
                pod.provider,
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
            "failed": "red",
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
            title=f"Pod Status: {pod.name}",
        )
        console.print(panel)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.Abort()


@pods.command("ssh")
@click.argument("pod_id")
@click.option(
    "--interactive", "-i", is_flag=True, help="Launch interactive SSH session"
)
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
            console.print(
                f"\n[dim]Copy and paste the command above to connect to your pod[/dim]"
            )
            console.print(
                f"[dim]Or use --interactive flag to launch SSH session directly[/dim]"
            )

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.Abort()


@pods.command("logs")
@click.argument("pod_id")
@click.option(
    "--lines", "-n", type=int, default=100, help="Number of log lines to retrieve"
)
@click.option("--follow", "-f", is_flag=True, help="Follow log output (if supported)")
def pod_logs(pod_id: str, lines: int, follow: bool):
    """Get logs from a pod."""
    try:
        manager = PrimeManager()

        if follow:
            console.print(
                "[yellow]Note: Follow mode may not be supported by all providers[/yellow]"
            )

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
            if not click.confirm(
                f"Are you sure you want to terminate pod '{pod.name}' ({pod_id})?"
            ):
                return

        success = manager.terminate_pod(pod_id)

        if success:
            console.print(f"[green]Pod {pod_id} terminated successfully[/green]")
        else:
            console.print(f"[red]Failed to terminate pod {pod_id}[/red]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.Abort()


@pod.command("setup")
@click.argument("name")
@click.argument("ssh_command")
@click.option("--run-setup", is_flag=True, help="Run automated setup script on pod")
@click.option(
    "--test-connection",
    is_flag=True,
    default=True,
    help="Test SSH connection (default: true)",
)
def setup_pod(name: str, ssh_command: str, run_setup: bool, test_connection: bool):
    """Configure and setup a new pod.

    Examples:
      pcm pod setup my-pod "root@192.168.1.100 -p 22"
      pcm pod setup gpu-server "ubuntu@server.com -i ~/.ssh/key"
    """
    try:
        config_manager = ConfigManager()
        ssh_manager = SSHManager(config_manager)

        console.print(f"[green]Setting up pod '{name}'...[/green]")

        # Validate and clean SSH command
        try:
            cleaned_ssh = ssh_manager._validate_ssh_command(ssh_command)
        except ValueError as e:
            console.print(f"[red]Invalid SSH command: {e}[/red]")
            raise click.Abort()

        # Test connection if requested
        if test_connection:
            console.print("Testing SSH connection...")
            if not ssh_manager.test_ssh_connection(cleaned_ssh):
                console.print("[red]✗ SSH connection failed[/red]")
                if not click.confirm("Continue anyway?"):
                    raise click.Abort()
            else:
                console.print("[green]✓ SSH connection successful[/green]")

        # Get pod information
        temp_pod = PodConfig(
            name=name,
            ssh_command=cleaned_ssh,
            provider="unknown",
            region="unknown",
            gpu_type="unknown",
            gpu_count=0,
            cost_per_hour=0.0,
            created_at="",
        )

        # Check pod status to get more info
        console.print("Gathering pod information...")
        try:
            status = ssh_manager.check_pod_status(temp_pod)
            if status.get("reachable"):
                provider = "custom"  # Default for manually configured pods
                region = status.get("hostname", "unknown")
                gpu_count = len(status.get("gpus", []))
                gpu_type = status["gpus"][0] if status.get("gpus") else "unknown"

                console.print(f"  Hostname: {status.get('hostname', 'unknown')}")
                console.print(f"  GPUs: {gpu_count} ({gpu_type})")
                console.print(
                    f"  Prime CLI: {'✓' if status.get('prime_cli_available') else '✗'}"
                )
            else:
                provider = region = gpu_type = "unknown"
                gpu_count = 0
                console.print(
                    f"[yellow]Warning: Could not gather pod info: {status.get('error', 'unknown')}[/yellow]"
                )
        except Exception as e:
            console.print(f"[yellow]Warning: Could not check pod status: {e}[/yellow]")
            provider = region = gpu_type = "unknown"
            gpu_count = 0

        # Add pod to configuration
        config_manager.add_pod(
            name=name,
            ssh_command=cleaned_ssh,
            provider=provider,
            region=region,
            gpu_type=gpu_type,
            gpu_count=gpu_count,
            cost_per_hour=0.0,  # Will be updated when pods are created
        )

        console.print(f"[green]✓ Pod '{name}' configured and set as active[/green]")

        # Run setup script if requested
        if run_setup:
            console.print("\n[bold]Running automated setup script...[/bold]")

            script_path = (
                Path(__file__).parent.parent.parent / "scripts" / "pod_setup.sh"
            )
            if not script_path.exists():
                console.print(f"[red]Setup script not found at {script_path}[/red]")
                return

            try:
                # Copy setup script to pod
                pod_config = config_manager.get_pod(name)
                ssh_manager.copy_file_to_pod(
                    pod_config, str(script_path), "~/pod_setup.sh"
                )

                # Run setup script
                console.print("Executing setup script on pod...")
                exit_code = ssh_manager.execute_ssh_command(
                    pod_config,
                    "chmod +x ~/pod_setup.sh && ~/pod_setup.sh",
                    interactive=True,
                )

                if exit_code == 0:
                    console.print(
                        "[green]✓ Setup script completed successfully[/green]"
                    )
                else:
                    console.print(
                        f"[yellow]Setup script exited with code {exit_code}[/yellow]"
                    )

            except Exception as e:
                console.print(f"[red]Setup script failed: {e}[/red]")

        # Show usage instructions
        console.print("\n[bold]Pod setup complete![/bold]")
        console.print(f"Active pod: [cyan]{name}[/cyan]")
        console.print("\nUseful commands:")
        console.print(
            "  [bold]pcm pod list[/bold]           # List all configured pods"
        )
        console.print("  [bold]pcm pod switch <name>[/bold]  # Switch active pod")
        console.print("  [bold]pcm pod shell[/bold]          # SSH into active pod")
        console.print("  [bold]pcm pod status[/bold]         # Check active pod status")
        console.print("  [bold]pcm resources list[/bold]     # List GPU resources")
        console.print("  [bold]pcm pods create[/bold]        # Create new compute pod")

    except Exception as e:
        console.print(f"[red]Error setting up pod: {e}[/red]")
        raise click.Abort()


@pod.command("list")
def list_configured_pods():
    """List all configured pods."""
    try:
        config_manager = ConfigManager()
        pods = config_manager.list_pods()
        active_pod = config_manager.get_active_pod()

        if not pods:
            console.print("[yellow]No pods configured.[/yellow]")
            console.print(
                "\nTo add a pod: [bold]pcm pod setup <name> <ssh_command>[/bold]"
            )
            console.print(
                'Example: [dim]pcm pod setup my-pod "root@192.168.1.100 -p 22"[/dim]'
            )
            return

        table = Table(title="Configured Pods")
        table.add_column("Name", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("SSH Command")
        table.add_column("Provider", style="blue")
        table.add_column("Region", style="magenta")
        table.add_column("GPUs", justify="right")

        for pod in pods:
            status_icon = "●" if active_pod and pod.name == active_pod.name else "○"
            status_text = (
                "active" if active_pod and pod.name == active_pod.name else "configured"
            )

            table.add_row(
                pod.name,
                f"{status_icon} {status_text}",
                pod.ssh_command[:50] + "..."
                if len(pod.ssh_command) > 50
                else pod.ssh_command,
                pod.provider,
                pod.region,
                str(pod.gpu_count) if pod.gpu_count > 0 else "unknown",
            )

        console.print(table)

        if active_pod:
            console.print(f"\n[bold]Active pod:[/bold] [cyan]{active_pod.name}[/cyan]")

    except Exception as e:
        console.print(f"[red]Error listing pods: {e}[/red]")
        raise click.Abort()


@pod.command("switch")
@click.argument("name")
def switch_pod(name: str):
    """Switch to a different pod."""
    try:
        config_manager = ConfigManager()

        if not config_manager.get_pod(name):
            console.print(f"[red]Pod '{name}' not found[/red]")

            # Show available pods
            pods = config_manager.list_pods()
            if pods:
                available = ", ".join([p.name for p in pods])
                console.print(f"Available pods: {available}")

            raise click.Abort()

        config_manager.set_active_pod(name)
        pod = config_manager.get_pod(name)

        console.print(f"[green]Switched to pod: [bold]{name}[/bold][/green]")
        console.print(f"SSH: {pod.ssh_command}")

    except Exception as e:
        console.print(f"[red]Error switching pods: {e}[/red]")
        raise click.Abort()


@pod.command("remove")
@click.argument("name")
@click.option("--yes", is_flag=True, help="Skip confirmation")
def remove_pod(name: str, yes: bool):
    """Remove a pod from configuration."""
    try:
        config_manager = ConfigManager()

        if not config_manager.get_pod(name):
            console.print(f"[red]Pod '{name}' not found[/red]")
            raise click.Abort()

        if not yes:
            if not click.confirm(f"Remove pod '{name}' from configuration?"):
                return

        config_manager.remove_pod(name)
        console.print(f"[green]Removed pod '{name}' from configuration[/green]")

        # Show new active pod if any
        active = config_manager.get_active_pod()
        if active:
            console.print(f"Active pod is now: [cyan]{active.name}[/cyan]")
        else:
            console.print("[yellow]No active pod remaining[/yellow]")

    except Exception as e:
        console.print(f"[red]Error removing pod: {e}[/red]")
        raise click.Abort()


@pod.command("shell")
@click.option("--pod", help="Pod name (uses active pod if not specified)")
def shell_to_pod(pod: Optional[str]):
    """Launch an interactive SSH session to a pod."""
    try:
        config_manager = ConfigManager()
        ssh_manager = SSHManager(config_manager)

        if pod:
            pod_config = config_manager.get_pod(pod)
            if not pod_config:
                console.print(f"[red]Pod '{pod}' not found[/red]")
                raise click.Abort()
        else:
            pod_config = config_manager.get_active_pod()
            if not pod_config:
                console.print("[red]No active pod configured[/red]")
                console.print(
                    "Set up a pod first: [bold]pcm pod setup <name> <ssh_command>[/bold]"
                )
                raise click.Abort()

        console.print(f"[green]Connecting to pod '{pod_config.name}'...[/green]")

        exit_code = ssh_manager.launch_ssh_session(pod_config)

        if exit_code == 0:
            console.print(
                f"[green]SSH session to '{pod_config.name}' completed[/green]"
            )
        else:
            console.print(f"[yellow]SSH session exited with code {exit_code}[/yellow]")

    except Exception as e:
        console.print(f"[red]Error connecting to pod: {e}[/red]")
        raise click.Abort()


@pod.command("status")
@click.option("--pod", help="Pod name (uses active pod if not specified)")
def pod_status_check(pod: Optional[str]):
    """Check the status of a pod."""
    try:
        config_manager = ConfigManager()
        ssh_manager = SSHManager(config_manager)

        if pod:
            pod_config = config_manager.get_pod(pod)
            if not pod_config:
                console.print(f"[red]Pod '{pod}' not found[/red]")
                raise click.Abort()
        else:
            pod_config = config_manager.get_active_pod()
            if not pod_config:
                console.print("[red]No active pod configured[/red]")
                raise click.Abort()

        console.print(f"[green]Checking status of pod '{pod_config.name}'...[/green]")

        status = ssh_manager.check_pod_status(pod_config)

        # Display status in a panel
        status_text = f"[bold]Pod:[/bold] {pod_config.name}\n"
        status_text += f"[bold]SSH:[/bold] {pod_config.ssh_command}\n\n"

        if status.get("reachable"):
            status_text += f"[green]✓ Reachable[/green]\n"
            status_text += (
                f"[bold]Hostname:[/bold] {status.get('hostname', 'unknown')}\n"
            )
            status_text += f"[bold]Uptime:[/bold] {status.get('uptime', 'unknown')}\n"

            gpus = status.get("gpus", [])
            if gpus:
                status_text += f"[bold]GPUs:[/bold] {len(gpus)}\n"
                for i, gpu in enumerate(gpus):
                    status_text += f"  GPU {i}: {gpu}\n"
            else:
                status_text += "[bold]GPUs:[/bold] None detected\n"

            prime_status = (
                "✓ Available"
                if status.get("prime_cli_available")
                else "✗ Not available"
            )
            status_text += f"[bold]Prime CLI:[/bold] {prime_status}\n"

        else:
            status_text += f"[red]✗ Not reachable[/red]\n"
            if status.get("error"):
                status_text += f"[bold]Error:[/bold] {status['error']}\n"

        panel = Panel.fit(
            status_text.strip(),
            title=f"Pod Status: {pod_config.name}",
            border_style="green" if status.get("reachable") else "red",
        )
        console.print(panel)

    except Exception as e:
        console.print(f"[red]Error checking pod status: {e}[/red]")
        raise click.Abort()


@pod.command("ssh")
@click.argument("command", nargs=-1)
@click.option("--pod", help="Pod name (uses active pod if not specified)")
@click.option("--interactive", "-i", is_flag=True, help="Run command interactively")
def ssh_command(command: tuple, pod: Optional[str], interactive: bool):
    """Execute a command on a pod via SSH.

    Examples:
      pcm pod ssh ls -la
      pcm pod ssh --interactive htop
      pcm pod ssh --pod my-pod "prime pods list"
    """
    try:
        config_manager = ConfigManager()
        ssh_manager = SSHManager(config_manager)

        if pod:
            pod_config = config_manager.get_pod(pod)
            if not pod_config:
                console.print(f"[red]Pod '{pod}' not found[/red]")
                raise click.Abort()
        else:
            pod_config = config_manager.get_active_pod()
            if not pod_config:
                console.print("[red]No active pod configured[/red]")
                raise click.Abort()

        if not command:
            # If no command specified, launch interactive shell
            console.print(
                f"[green]Launching shell on pod '{pod_config.name}'...[/green]"
            )
            ssh_manager.launch_ssh_session(pod_config)
            return

        cmd_str = " ".join(command)

        if interactive:
            exit_code = ssh_manager.execute_ssh_command(
                pod_config, cmd_str, interactive=True
            )
            if exit_code != 0:
                console.print(f"[yellow]Command exited with code {exit_code}[/yellow]")
        else:
            output = ssh_manager.execute_ssh_command(
                pod_config, cmd_str, interactive=False
            )
            console.print(output)

    except Exception as e:
        console.print(f"[red]Error executing SSH command: {e}[/red]")
        raise click.Abort()


if __name__ == "__main__":
    main()

