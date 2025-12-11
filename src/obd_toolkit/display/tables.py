"""Table display utilities for OBD toolkit."""

from typing import List, Optional, Any, Dict
from rich.table import Table
from rich.console import Console

from ..models.dtc import DTCInfo, DTCReadResult, DTCSeverity
from ..models.pid import PIDValue, PIDInfo
from ..models.vehicle import VehicleInfo
from ..models.session import DiagnosticSession, AnalysisResult, AnalysisFinding


class TableDisplay:
    """Create and display formatted tables."""

    def __init__(self, console: Optional[Console] = None):
        self._console = console or Console()

    def dtc_table(self, dtcs: List[DTCInfo], title: str = "Diagnostic Trouble Codes") -> Table:
        """Create a table of DTCs."""
        table = Table(title=title, show_header=True, header_style="bold cyan")

        table.add_column("Code", style="yellow bold", width=8)
        table.add_column("Type", style="dim", width=10)
        table.add_column("Severity", width=10)
        table.add_column("Description", style="white")
        table.add_column("System", style="dim")

        for dtc in dtcs:
            severity_style = {
                DTCSeverity.CRITICAL: "red bold",
                DTCSeverity.WARNING: "yellow",
                DTCSeverity.INFO: "cyan",
            }.get(dtc.severity, "white")

            table.add_row(
                dtc.code,
                dtc.dtc_type.value,
                f"[{severity_style}]{dtc.severity.value}[/{severity_style}]",
                dtc.description[:50] + "..." if len(dtc.description) > 50 else dtc.description,
                dtc.system,
            )

        return table

    def dtc_summary_table(self, result: DTCReadResult) -> Table:
        """Create a summary table of DTC reading results."""
        table = Table(title="DTC Summary", show_header=True, header_style="bold cyan")

        table.add_column("Category", style="cyan")
        table.add_column("Count", justify="right")
        table.add_column("Status")

        mil_status = "[red bold]ON[/red bold]" if result.mil_status else "[green]OFF[/green]"

        table.add_row("MIL (Check Engine)", "-", mil_status)
        table.add_row(
            "Stored Codes",
            str(len(result.stored_codes)),
            "[red]Issues Found[/red]" if result.stored_codes else "[green]None[/green]"
        )
        table.add_row(
            "Pending Codes",
            str(len(result.pending_codes)),
            "[yellow]Monitoring[/yellow]" if result.pending_codes else "[green]None[/green]"
        )
        table.add_row(
            "Permanent Codes",
            str(len(result.permanent_codes)),
            "[red]Needs Repair[/red]" if result.permanent_codes else "[green]None[/green]"
        )

        return table

    def pid_table(self, values: List[PIDValue], title: str = "Live Data") -> Table:
        """Create a table of PID values."""
        table = Table(title=title, show_header=True, header_style="bold cyan")

        table.add_column("PID", style="cyan bold", width=25)
        table.add_column("Value", justify="right", width=15)
        table.add_column("Unit", style="dim", width=10)
        table.add_column("Status", width=10)

        for pv in values:
            status = "[green]OK[/green]" if pv.is_valid else f"[red]{pv.error_message or 'Error'}[/red]"

            if pv.value is not None:
                if isinstance(pv.value, float):
                    value_str = f"{pv.value:.2f}"
                else:
                    value_str = str(pv.value)
            else:
                value_str = "N/A"

            table.add_row(pv.name, value_str, pv.unit, status)

        return table

    def pid_info_table(self, pids: List[PIDInfo], title: str = "Available PIDs") -> Table:
        """Create a table of PID definitions."""
        table = Table(title=title, show_header=True, header_style="bold cyan")

        table.add_column("PID", style="cyan bold", width=25)
        table.add_column("Description", width=40)
        table.add_column("Unit", style="dim", width=10)
        table.add_column("Range", style="dim", width=20)
        table.add_column("Supported", width=10)

        for pid in pids:
            range_str = ""
            if pid.min_value is not None and pid.max_value is not None:
                range_str = f"{pid.min_value} - {pid.max_value}"

            supported = "[green]Yes[/green]" if pid.is_supported else "[dim]No[/dim]"

            table.add_row(
                pid.name,
                pid.description[:40] if pid.description else "-",
                pid.unit.value if pid.unit else "-",
                range_str,
                supported,
            )

        return table

    def vehicle_info_table(self, info: VehicleInfo) -> Table:
        """Create a table of vehicle information."""
        table = Table(title="Vehicle Information", show_header=True, header_style="bold cyan")

        table.add_column("Property", style="cyan")
        table.add_column("Value", style="white")

        table.add_row("VIN", info.vin)
        table.add_row("Manufacturer", info.manufacturer)
        table.add_row("Make", info.make)
        table.add_row("Model", info.model if info.model != "Unknown" else "-")
        table.add_row("Model Year", str(info.model_year) if info.model_year else "-")
        table.add_row("Country", info.country)
        table.add_row("Body Class", info.body_class if info.body_class != "Unknown" else "-")
        table.add_row("Engine Type", info.engine_type if info.engine_type != "Unknown" else "-")
        table.add_row("Fuel Type", info.fuel_type if info.fuel_type != "Unknown" else "-")
        table.add_row("Drive Type", info.drive_type if info.drive_type != "Unknown" else "-")

        if not info.is_valid:
            table.add_row("[red]Validation[/red]", "[red]Invalid VIN[/red]")
            for err in info.validation_errors:
                table.add_row("", f"[red]- {err}[/red]")

        return table

    def analysis_table(self, result: AnalysisResult) -> Table:
        """Create a table of analysis findings."""
        table = Table(
            title=f"{result.analyzer_name} Results",
            show_header=True,
            header_style="bold cyan"
        )

        table.add_column("Severity", width=10)
        table.add_column("Finding", width=30)
        table.add_column("Description", width=40)
        table.add_column("Confidence", justify="right", width=10)

        for finding in result.findings:
            severity_style = {
                "critical": "red bold",
                "warning": "yellow",
                "info": "cyan",
            }.get(finding.severity, "white")

            table.add_row(
                f"[{severity_style}]{finding.severity.upper()}[/{severity_style}]",
                finding.title,
                finding.description[:40] + "..." if len(finding.description) > 40 else finding.description,
                f"{finding.confidence * 100:.0f}%",
            )

        return table

    def session_table(self, sessions: List[Dict[str, Any]], title: str = "Diagnostic Sessions") -> Table:
        """Create a table of diagnostic sessions."""
        table = Table(title=title, show_header=True, header_style="bold cyan")

        table.add_column("ID", style="cyan bold", width=10)
        table.add_column("Date", width=20)
        table.add_column("Vehicle", width=25)
        table.add_column("DTCs", justify="right", width=8)
        table.add_column("Samples", justify="right", width=10)
        table.add_column("Duration", width=12)

        for session in sessions:
            table.add_row(
                session.get("session_id", "-"),
                session.get("start_time", "-"),
                session.get("vehicle", "-"),
                str(session.get("dtc_count", 0)),
                str(session.get("sample_count", 0)),
                session.get("duration", "-"),
            )

        return table

    def adapters_table(self, adapters: List[Dict[str, Any]]) -> Table:
        """Create a table of detected adapters."""
        table = Table(title="Detected OBD2 Adapters", show_header=True, header_style="bold cyan")

        table.add_column("Port", style="cyan bold")
        table.add_column("Type", width=20)
        table.add_column("Description", width=35)
        table.add_column("Manufacturer", width=20)

        for adapter in adapters:
            table.add_row(
                adapter.get("port", "-"),
                adapter.get("type", "Unknown"),
                adapter.get("description", "-"),
                adapter.get("manufacturer", "-"),
            )

        return table

    def show(self, table: Table) -> None:
        """Display a table to the console."""
        self._console.print(table)
        self._console.print()
