"""Console output utilities using Rich."""

from typing import Optional, List, Any
from rich.console import Console as RichConsole
from rich.panel import Panel
from rich.text import Text
from rich.style import Style
from rich.theme import Theme

# Custom theme for OBD toolkit
OBD_THEME = Theme({
    "info": "cyan",
    "success": "green",
    "warning": "yellow",
    "error": "red bold",
    "critical": "red bold reverse",
    "highlight": "magenta",
    "muted": "dim",
    "pid.name": "cyan bold",
    "pid.value": "green",
    "pid.unit": "dim",
    "dtc.code": "yellow bold",
    "dtc.description": "white",
    "dtc.critical": "red bold",
    "dtc.warning": "yellow",
    "dtc.info": "cyan",
    "status.connected": "green bold",
    "status.disconnected": "red",
    "status.connecting": "yellow",
    "header": "bold blue",
    "subheader": "bold cyan",
})


class Console:
    """Enhanced console output for OBD toolkit."""

    def __init__(self):
        self._console = RichConsole(theme=OBD_THEME)

    @property
    def rich_console(self) -> RichConsole:
        """Get the underlying Rich console."""
        return self._console

    def print(self, *args, **kwargs) -> None:
        """Print to console."""
        self._console.print(*args, **kwargs)

    def info(self, message: str, prefix: str = "INFO") -> None:
        """Print info message."""
        self._console.print(f"[info][{prefix}][/info] {message}")

    def success(self, message: str, prefix: str = "OK") -> None:
        """Print success message."""
        self._console.print(f"[success][{prefix}][/success] {message}")

    def warning(self, message: str, prefix: str = "WARN") -> None:
        """Print warning message."""
        self._console.print(f"[warning][{prefix}][/warning] {message}")

    def error(self, message: str, prefix: str = "ERROR") -> None:
        """Print error message."""
        self._console.print(f"[error][{prefix}][/error] {message}")

    def critical(self, message: str, prefix: str = "CRITICAL") -> None:
        """Print critical message."""
        self._console.print(f"[critical][{prefix}][/critical] {message}")

    def header(self, title: str, subtitle: Optional[str] = None) -> None:
        """Print a section header."""
        self._console.print()
        self._console.print(f"[header]{title}[/header]")
        if subtitle:
            self._console.print(f"[muted]{subtitle}[/muted]")
        self._console.print()

    def subheader(self, title: str) -> None:
        """Print a subsection header."""
        self._console.print(f"\n[subheader]{title}[/subheader]")

    def panel(
        self,
        content: str,
        title: Optional[str] = None,
        style: str = "cyan",
        expand: bool = False
    ) -> None:
        """Print content in a panel."""
        self._console.print(Panel(content, title=title, style=style, expand=expand))

    def status_panel(self, title: str, items: dict, style: str = "cyan") -> None:
        """Print a status panel with key-value pairs."""
        lines = []
        for key, value in items.items():
            lines.append(f"[bold]{key}:[/bold] {value}")
        content = "\n".join(lines)
        self.panel(content, title=title, style=style)

    def rule(self, title: str = "", style: str = "dim") -> None:
        """Print a horizontal rule."""
        self._console.rule(title, style=style)

    def newline(self, count: int = 1) -> None:
        """Print blank lines."""
        for _ in range(count):
            self._console.print()

    def clear(self) -> None:
        """Clear the console."""
        self._console.clear()

    def print_dtc(self, code: str, description: str, severity: str = "warning") -> None:
        """Print a DTC code with appropriate styling."""
        severity_style = f"dtc.{severity}"
        self._console.print(
            f"  [{severity_style}]{code}[/{severity_style}] - [dtc.description]{description}[/dtc.description]"
        )

    def print_pid(self, name: str, value: Any, unit: str = "") -> None:
        """Print a PID value."""
        unit_str = f" [pid.unit]{unit}[/pid.unit]" if unit else ""
        self._console.print(
            f"  [pid.name]{name}:[/pid.name] [pid.value]{value}[/pid.value]{unit_str}"
        )

    def print_connection_status(self, connected: bool, details: str = "") -> None:
        """Print connection status."""
        if connected:
            status = "[status.connected]CONNECTED[/status.connected]"
        else:
            status = "[status.disconnected]DISCONNECTED[/status.disconnected]"

        self._console.print(f"Status: {status}")
        if details:
            self._console.print(f"  [muted]{details}[/muted]")

    def confirm(self, message: str, default: bool = False) -> bool:
        """Ask for confirmation."""
        default_str = "Y/n" if default else "y/N"
        response = self._console.input(f"{message} [{default_str}]: ").strip().lower()

        if not response:
            return default
        return response in ("y", "yes")

    def print_banner(self) -> None:
        """Print the OBD toolkit banner."""
        banner = """
[bold cyan]  ___  ____  ____    _____           _ _    _ _
 / _ \\| __ )|  _ \\  |_   _|__   ___ | | | _(_) |_
| | | |  _ \\| | | |   | |/ _ \\ / _ \\| | |/ / | __|
| |_| | |_) | |_| |   | | (_) | (_) | |   <| | |_
 \\___/|____/|____/    |_|\\___/ \\___/|_|_\\_\\_|\\__|[/bold cyan]

[dim]OBD2 Diagnostic Toolkit v1.0.0[/dim]
"""
        self._console.print(banner)


# Global console instance
console = Console()
