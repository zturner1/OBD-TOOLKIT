"""Live data display for real-time monitoring."""

import time
from typing import Dict, List, Optional, Callable
from datetime import datetime
from threading import Event

from rich.console import Console, Group
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn

from ..models.pid import PIDValue


class LiveDisplay:
    """Real-time dashboard display for OBD monitoring."""

    def __init__(self, console: Optional[Console] = None):
        self._console = console or Console()
        self._live: Optional[Live] = None
        self._stop_event = Event()
        self._last_update: Optional[datetime] = None
        self._sample_count = 0
        self._error_count = 0

    def create_dashboard(
        self,
        pid_values: Dict[str, PIDValue],
        vehicle_info: Optional[str] = None,
        connection_info: Optional[str] = None,
    ) -> Panel:
        """Create a dashboard panel with current values."""

        # Main data table
        table = Table(show_header=True, header_style="bold cyan", expand=True)
        table.add_column("Parameter", style="cyan")
        table.add_column("Value", justify="right", style="green bold")
        table.add_column("Unit", style="dim")

        for pid_name, pv in pid_values.items():
            if pv.value is not None:
                if isinstance(pv.value, float):
                    value_str = f"{pv.value:.1f}"
                else:
                    value_str = str(pv.value)
                style = "green bold"
            else:
                value_str = "N/A"
                style = "red"

            table.add_row(
                pv.name,
                f"[{style}]{value_str}[/{style}]",
                pv.unit,
            )

        # Status line
        now = datetime.now().strftime("%H:%M:%S")
        status_parts = [f"[dim]Updated: {now}[/dim]"]

        if self._sample_count > 0:
            status_parts.append(f"[dim]Samples: {self._sample_count}[/dim]")

        if self._error_count > 0:
            status_parts.append(f"[red]Errors: {self._error_count}[/red]")

        status_line = " | ".join(status_parts)

        # Header info
        header_parts = []
        if vehicle_info:
            header_parts.append(vehicle_info)
        if connection_info:
            header_parts.append(connection_info)

        header = " | ".join(header_parts) if header_parts else "Live Monitor"

        # Combine into panel
        content = Group(table, Text(status_line))

        return Panel(
            content,
            title=f"[bold cyan]{header}[/bold cyan]",
            subtitle="[dim]Press Ctrl+C to stop[/dim]",
            border_style="cyan",
        )

    def create_gauge_display(self, pid_values: Dict[str, PIDValue]) -> Panel:
        """Create a gauge-style display for key metrics."""
        lines = []

        # RPM gauge
        if "RPM" in pid_values:
            rpm = pid_values["RPM"].numeric_value or 0
            rpm_pct = min(rpm / 8000 * 100, 100)
            rpm_bar = self._make_bar(rpm_pct, 30, color="green" if rpm < 5000 else "yellow" if rpm < 6500 else "red")
            lines.append(f"RPM:   {rpm_bar} {rpm:.0f}")

        # Speed gauge
        if "SPEED" in pid_values:
            speed = pid_values["SPEED"].numeric_value or 0
            speed_pct = min(speed / 200 * 100, 100)
            speed_bar = self._make_bar(speed_pct, 30)
            lines.append(f"Speed: {speed_bar} {speed:.0f} km/h")

        # Engine load
        if "ENGINE_LOAD" in pid_values:
            load = pid_values["ENGINE_LOAD"].numeric_value or 0
            load_bar = self._make_bar(load, 30, color="green" if load < 70 else "yellow" if load < 90 else "red")
            lines.append(f"Load:  {load_bar} {load:.0f}%")

        # Coolant temp
        if "COOLANT_TEMP" in pid_values:
            temp = pid_values["COOLANT_TEMP"].numeric_value or 0
            temp_pct = max(0, min((temp - 40) / 80 * 100, 100))
            color = "cyan" if temp < 80 else "green" if temp < 100 else "yellow" if temp < 110 else "red"
            temp_bar = self._make_bar(temp_pct, 30, color=color)
            lines.append(f"Temp:  {temp_bar} {temp:.0f}C")

        # Throttle
        if "THROTTLE_POS" in pid_values:
            throttle = pid_values["THROTTLE_POS"].numeric_value or 0
            throttle_bar = self._make_bar(throttle, 30, color="cyan")
            lines.append(f"Thrtl: {throttle_bar} {throttle:.0f}%")

        content = "\n".join(lines) if lines else "[dim]No gauge data available[/dim]"

        return Panel(content, title="[bold]Gauges[/bold]", border_style="green")

    def _make_bar(self, percentage: float, width: int = 20, color: str = "green") -> str:
        """Create a text-based progress bar."""
        filled = int(width * percentage / 100)
        empty = width - filled
        return f"[{color}]{'█' * filled}[/{color}][dim]{'░' * empty}[/dim]"

    def start_monitoring(
        self,
        get_values: Callable[[], Dict[str, PIDValue]],
        refresh_rate: float = 0.5,
        vehicle_info: Optional[str] = None,
        connection_info: Optional[str] = None,
        show_gauges: bool = True,
    ) -> None:
        """
        Start live monitoring display.

        Args:
            get_values: Callback to get current PID values
            refresh_rate: Seconds between updates
            vehicle_info: Vehicle info to display in header
            connection_info: Connection info to display
            show_gauges: Whether to show gauge display
        """
        self._stop_event.clear()
        self._sample_count = 0
        self._error_count = 0

        def generate_display():
            try:
                values = get_values()
                self._sample_count += 1

                if show_gauges and len(values) >= 3:
                    # Create layout with gauges
                    layout = Layout()
                    layout.split_column(
                        Layout(name="main", ratio=2),
                        Layout(name="gauges", ratio=1),
                    )
                    layout["main"].update(self.create_dashboard(values, vehicle_info, connection_info))
                    layout["gauges"].update(self.create_gauge_display(values))
                    return layout
                else:
                    return self.create_dashboard(values, vehicle_info, connection_info)

            except Exception as e:
                self._error_count += 1
                return Panel(f"[red]Error: {e}[/red]", title="Monitor Error", border_style="red")

        with Live(generate_display(), console=self._console, refresh_per_second=1/refresh_rate) as live:
            self._live = live
            while not self._stop_event.is_set():
                try:
                    live.update(generate_display())
                    time.sleep(refresh_rate)
                except KeyboardInterrupt:
                    break

        self._live = None

    def stop_monitoring(self) -> None:
        """Stop live monitoring."""
        self._stop_event.set()

    def show_connecting(self, port: str) -> Live:
        """Show connecting spinner."""
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Connecting to {task.description}...[/cyan]"),
            console=self._console,
        )
        progress.add_task(description=port, total=None)
        return Live(progress, console=self._console, refresh_per_second=10)

    def show_scanning(self, message: str = "Scanning for adapters") -> Live:
        """Show scanning spinner."""
        progress = Progress(
            SpinnerColumn(),
            TextColumn(f"[cyan]{message}...[/cyan]"),
            console=self._console,
        )
        progress.add_task(description="", total=None)
        return Live(progress, console=self._console, refresh_per_second=10)
