"""Textual TUI interface for Prime Compute Manager."""

import asyncio
from datetime import datetime
from typing import List, Optional
from rich.text import Text

from textual import on
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Static,
    Select,
    ProgressBar,
)
from textual.coordinate import Coordinate

from .manager import PrimeManager
from .models import GPUResource, Pod


class ResourceTable(DataTable):
    """Interactive table for displaying GPU resources."""
    
    def __init__(self):
        super().__init__()
        self.cursor_type = "row"
        self.zebra_stripes = True
        
        # Add columns
        self.add_columns(
            "GPU Type",
            "Available", 
            "Total",
            "Cost/Hour",
            "Provider",
            "Region",
            "Prime ID"
        )
    
    def update_resources(self, resources: List[GPUResource]) -> None:
        """Update the table with new resource data."""
        self.clear()
        
        for resource in resources:
            self.add_row(
                resource.gpu_type.value,
                str(resource.available_count),
                str(resource.total_count),
                f"${resource.cost_per_hour:.2f}",
                resource.provider,
                resource.region,
                resource.prime_id or "N/A",
                key=resource.prime_id
            )
    
    def get_selected_resource(self, resources: List[GPUResource]) -> Optional[GPUResource]:
        """Get the currently selected resource."""
        if self.cursor_coordinate.row < len(resources):
            return resources[self.cursor_coordinate.row]
        return None


class PodTable(DataTable):
    """Interactive table for displaying active pods."""
    
    def __init__(self):
        super().__init__()
        self.cursor_type = "row"
        self.zebra_stripes = True
        
        # Add columns
        self.add_columns(
            "Name",
            "Status", 
            "GPU",
            "Runtime",
            "Cost",
            "Provider"
        )
    
    def update_pods(self, pods: List[Pod]) -> None:
        """Update the table with pod data."""
        self.clear()
        
        for pod in pods:
            runtime_hours = pod.runtime_hours
            runtime_str = f"{runtime_hours:.1f}h" if runtime_hours > 0 else "0h"
            
            # Color code status
            status_text = Text(pod.status.value)
            if pod.status.value == "running":
                status_text.stylize("green")
            elif pod.status.value == "creating":
                status_text.stylize("yellow")
            elif pod.status.value == "failed":
                status_text.stylize("red")
            
            self.add_row(
                pod.name,
                status_text,
                f"{pod.gpu_type.value} x{pod.gpu_count}",
                runtime_str,
                f"${pod.total_cost:.2f}",
                pod.provider,
                key=pod.id
            )


class FilterPanel(Container):
    """Panel for filtering resources."""
    
    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("🔍 Resource Filters", classes="filter-title")
            yield Input(placeholder="GPU Type (e.g., H100_80GB)", id="gpu_type_filter")
            yield Input(placeholder="Max Cost/Hour (e.g., 5.0)", id="max_cost_filter") 
            yield Input(placeholder="Min GPUs (e.g., 2)", id="min_count_filter")
            yield Input(placeholder="Provider", id="provider_filter")
            yield Button("Apply Filters", id="apply_filters", variant="primary")
            yield Button("Clear Filters", id="clear_filters")


class PrimeManagerTUI(App):
    """Main TUI application for Prime Compute Manager."""
    
    CSS = """
    Screen {
        layout: grid;
        grid-size: 3 3;
        grid-gutter: 1;
    }
    
    #resource_panel {
        column-span: 2;
        row-span: 2;
        border: solid $primary;
    }
    
    #filter_panel {
        row-span: 2;
        border: solid $accent;
    }
    
    #pod_panel {
        column-span: 2;
        border: solid $warning;
    }
    
    #status_panel {
        border: solid $success;
    }
    
    .filter-title {
        text-align: center;
        margin: 1;
        text-style: bold;
    }
    
    #status_label {
        text-align: center;
        margin: 1;
    }
    
    DataTable {
        height: 100%;
    }
    
    .panel-title {
        text-align: center;
        text-style: bold;
        background: $surface;
        margin-bottom: 1;
    }
    """
    
    BINDINGS = [
        ("r", "refresh", "Refresh"),
        ("c", "create_pod", "Create Pod"),
        ("q", "quit", "Quit"),
        ("d", "toggle_dark", "Toggle Dark Mode"),
        ("f", "focus_filter", "Focus Filter"),
    ]
    
    def __init__(self):
        super().__init__()
        self.manager = PrimeManager()
        self.resources: List[GPUResource] = []
        self.pods: List[Pod] = []
        self.auto_refresh = True
    
    def compose(self) -> ComposeResult:
        """Create the TUI layout."""
        yield Header()
        
        with Container(id="resource_panel"):
            yield Label("🚀 Available GPU Resources", classes="panel-title") 
            yield ResourceTable(id="resource_table")
        
        with Container(id="filter_panel"):
            yield FilterPanel()
        
        with Container(id="pod_panel"):
            yield Label("🔧 Active Pods", classes="panel-title")
            yield PodTable(id="pod_table")
        
        with Container(id="status_panel"):
            yield Label("📊 Status", classes="panel-title")
            yield Label("Ready", id="status_label")
            yield ProgressBar(id="refresh_progress", show_eta=False)
        
        yield Footer()
    
    async def on_mount(self) -> None:
        """Initialize the application."""
        await self.refresh_data()
        
        # Set up auto-refresh every 30 seconds
        self.set_interval(30, self.auto_refresh_data)
    
    async def auto_refresh_data(self) -> None:
        """Auto-refresh data if enabled."""
        if self.auto_refresh:
            await self.refresh_data()
    
    async def refresh_data(self) -> None:
        """Refresh resource and pod data."""
        status_label = self.query_one("#status_label", Label)
        progress = self.query_one("#refresh_progress", ProgressBar)
        
        try:
            status_label.update("🔄 Refreshing resources...")
            progress.advance(25)
            
            # Get current filter values
            gpu_type = self.query_one("#gpu_type_filter", Input).value or None
            max_cost_str = self.query_one("#max_cost_filter", Input).value
            min_count_str = self.query_one("#min_count_filter", Input).value
            provider = self.query_one("#provider_filter", Input).value or None
            
            max_cost = float(max_cost_str) if max_cost_str else None
            min_count = int(min_count_str) if min_count_str else 1
            
            # Fetch resources
            self.resources = self.manager.find_gpus(
                gpu_type=gpu_type,
                min_count=min_count,
                max_cost_per_hour=max_cost,
                provider=provider
            )
            progress.advance(50)
            
            status_label.update("🔄 Refreshing pods...")
            # Fetch pods
            self.pods = self.manager.list_pods()
            progress.advance(75)
            
            # Update tables
            resource_table = self.query_one("#resource_table", ResourceTable)
            resource_table.update_resources(self.resources)
            
            pod_table = self.query_one("#pod_table", PodTable)
            pod_table.update_pods(self.pods)
            
            progress.advance(100)
            
            # Update status
            total_cost = sum(pod.total_cost for pod in self.pods)
            active_pods = len([p for p in self.pods if p.status.value == "running"])
            
            status_label.update(
                f"✅ {len(self.resources)} resources, {active_pods} active pods, ${total_cost:.2f} total cost"
            )
            
        except Exception as e:
            status_label.update(f"❌ Error: {str(e)}")
        finally:
            progress.progress = 0
    
    @on(Button.Pressed, "#apply_filters")
    async def apply_filters(self) -> None:
        """Apply resource filters."""
        await self.refresh_data()
    
    @on(Button.Pressed, "#clear_filters")
    async def clear_filters(self) -> None:
        """Clear all filters."""
        self.query_one("#gpu_type_filter", Input).value = ""
        self.query_one("#max_cost_filter", Input).value = ""
        self.query_one("#min_count_filter", Input).value = ""
        self.query_one("#provider_filter", Input).value = ""
        await self.refresh_data()
    
    def action_refresh(self) -> None:
        """Refresh data action."""
        self.run_worker(self.refresh_data())
    
    def action_create_pod(self) -> None:
        """Create pod from selected resource."""
        resource_table = self.query_one("#resource_table", ResourceTable)
        selected_resource = resource_table.get_selected_resource(self.resources)
        
        if selected_resource:
            self.run_worker(self.create_pod_from_resource(selected_resource))
        else:
            status_label = self.query_one("#status_label", Label)
            status_label.update("❌ No resource selected")
    
    async def create_pod_from_resource(self, resource: GPUResource) -> None:
        """Create a pod from the selected resource."""
        status_label = self.query_one("#status_label", Label)
        
        try:
            status_label.update(f"🚀 Creating pod with {resource.gpu_type.value}...")
            
            if resource.prime_id:
                pod = self.manager.create_pod_from_config(
                    prime_id=resource.prime_id,
                    name=f"tui-pod-{datetime.now().strftime('%H%M%S')}"
                )
            else:
                pod = self.manager.create_pod(
                    gpu_type=resource.gpu_type.value,
                    gpu_count=1,
                    name=f"tui-pod-{datetime.now().strftime('%H%M%S')}"
                )
            
            status_label.update(f"✅ Created pod: {pod.name}")
            await self.refresh_data()
            
        except Exception as e:
            status_label.update(f"❌ Failed to create pod: {str(e)}")
    
    def action_focus_filter(self) -> None:
        """Focus the GPU type filter input."""
        self.query_one("#gpu_type_filter", Input).focus()
    
    def action_toggle_dark(self) -> None:
        """Toggle dark mode."""
        self.dark = not self.dark


def run_tui() -> None:
    """Run the TUI application."""
    app = PrimeManagerTUI()
    app.run()


if __name__ == "__main__":
    run_tui()