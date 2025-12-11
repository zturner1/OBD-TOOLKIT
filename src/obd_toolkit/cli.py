"""OBD Toolkit CLI application."""

import sys
from typing import Optional, List
from pathlib import Path

import typer
from rich.console import Console

from .connection.manager import ConnectionManager, get_connection_manager, ConnectionState
from .connection.adapter import AdapterDetector
from .collectors.dtc import DTCCollector
from .collectors.pid import PIDCollector
from .collectors.vin import VINCollector
from .collectors.live import LiveDataCollector
from .decoders.dtc import DTCDecoder
from .decoders.vin import VINDecoder
from .display.console import console as display_console
from .display.tables import TableDisplay
from .display.live import LiveDisplay
from .models.pid import PID_PRESETS
from .storage.logger import SessionLogger
from .storage.history import HistoryManager


# Create Typer apps
app = typer.Typer(
    name="obd-toolkit",
    help="OBD2 Diagnostic Toolkit - Read, analyze, and clear vehicle diagnostic data",
    no_args_is_help=True,
)

dtc_app = typer.Typer(help="Diagnostic Trouble Code operations")
pid_app = typer.Typer(help="Parameter ID operations")
log_app = typer.Typer(help="Data logging operations")
history_app = typer.Typer(help="Historical data management")
analyze_app = typer.Typer(help="Data analysis commands")

app.add_typer(dtc_app, name="dtc")
app.add_typer(pid_app, name="pid")
app.add_typer(log_app, name="log")
app.add_typer(history_app, name="history")
app.add_typer(analyze_app, name="analyze")

# Global state
_connection_manager: Optional[ConnectionManager] = None
_table_display = TableDisplay(Console())


def get_manager() -> ConnectionManager:
    """Get or create connection manager."""
    global _connection_manager
    if _connection_manager is None:
        _connection_manager = ConnectionManager()
    return _connection_manager


def require_connection(func):
    """Decorator to ensure connection before running command."""
    def wrapper(*args, **kwargs):
        manager = get_manager()
        if not manager.is_car_connected:
            display_console.error("Not connected to vehicle. Run 'obd-toolkit connect' first.")
            raise typer.Exit(1)
        return func(*args, **kwargs)
    return wrapper


# ============ Main Commands ============

@app.command()
def connect(
    port: Optional[str] = typer.Option(None, "--port", "-p", help="Serial port (auto-detect if not specified)"),
    baudrate: int = typer.Option(38400, "--baudrate", "-b", help="Baud rate"),
    protocol: Optional[str] = typer.Option(None, "--protocol", help="Force OBD protocol"),
    timeout: float = typer.Option(3.0, "--timeout", "-t", help="Connection timeout in seconds"),
):
    """Connect to an OBD2 adapter."""
    display_console.print_banner()

    manager = get_manager()
    live_display = LiveDisplay()

    if port is None:
        display_console.info("Scanning for OBD2 adapters...")
        adapters = AdapterDetector.detect_all()

        if not adapters:
            display_console.error("No OBD2 adapters found.")
            display_console.info("Make sure your adapter is connected and try specifying a port with --port")
            raise typer.Exit(1)

        # Show detected adapters
        adapter_data = [
            {"port": a.port, "type": a.adapter_type.value, "description": a.description, "manufacturer": a.manufacturer}
            for a in adapters
        ]
        _table_display.show(_table_display.adapters_table(adapter_data))

        port = adapters[0].port
        display_console.info(f"Using {port}")

    display_console.info(f"Connecting to {port}...")

    result = manager.connect(port=port, baudrate=baudrate, protocol=protocol, timeout=timeout)

    if result.success:
        if result.state == ConnectionState.CAR_CONNECTED:
            display_console.success(f"Connected to vehicle via {result.protocol}")
        else:
            display_console.warning("Connected to adapter but vehicle not responding (ignition may be off)")
    else:
        display_console.error(f"Connection failed: {result.error}")
        raise typer.Exit(1)


@app.command()
def disconnect():
    """Disconnect from OBD2 adapter."""
    manager = get_manager()
    manager.disconnect()
    display_console.success("Disconnected from OBD2 adapter")


@app.command()
def status():
    """Show connection and vehicle status."""
    manager = get_manager()
    status_info = manager.get_status_info()

    display_console.header("Connection Status")

    if manager.is_connected:
        display_console.print_connection_status(True, f"Protocol: {status_info['protocol']}")

        if status_info['adapter']:
            display_console.subheader("Adapter")
            display_console.print(f"  Port: {status_info['adapter']['port']}")
            display_console.print(f"  Type: {status_info['adapter']['type']}")

        display_console.print(f"\n  Supported commands: {status_info['supported_commands_count']}")

        # Try to get VIN if connected to car
        if manager.is_car_connected:
            try:
                vin_collector = VINCollector(manager)
                vin = vin_collector.read_vin()
                if vin:
                    display_console.print(f"  VIN: {vin}")
            except:
                pass
    else:
        display_console.print_connection_status(False)
        display_console.info("Run 'obd-toolkit connect' to connect to an adapter")


@app.command()
def scan():
    """Scan for available OBD2 adapters."""
    display_console.header("Scanning for OBD2 Adapters")

    adapters = AdapterDetector.detect_all()

    if not adapters:
        display_console.warning("No OBD2 adapters found")
        display_console.info("Make sure your adapter is plugged in")
        return

    adapter_data = [
        {"port": a.port, "type": a.adapter_type.value, "description": a.description, "manufacturer": a.manufacturer}
        for a in adapters
    ]
    _table_display.show(_table_display.adapters_table(adapter_data))

    display_console.info(f"Found {len(adapters)} adapter(s)")


@app.command()
def vin(
    online: bool = typer.Option(False, "--online", "-o", help="Use NHTSA API for detailed info"),
):
    """Read and decode Vehicle Identification Number."""
    manager = get_manager()

    if not manager.is_car_connected:
        display_console.error("Not connected to vehicle")
        raise typer.Exit(1)

    display_console.header("Vehicle Information")

    collector = VINCollector(manager)
    info = collector.get_vehicle_info(use_online=online)

    if info:
        _table_display.show(_table_display.vehicle_info_table(info))
    else:
        display_console.error("Could not read VIN from vehicle")


@app.command()
def monitor(
    pids: Optional[str] = typer.Option(None, "--pids", "-p", help="Comma-separated PIDs to monitor"),
    preset: Optional[str] = typer.Option(None, "--preset", help="PID preset (engine, fuel, performance, economy, all)"),
    interval: int = typer.Option(250, "--interval", "-i", help="Update interval in ms"),
    no_gauges: bool = typer.Option(False, "--no-gauges", help="Disable gauge display"),
):
    """Live monitoring dashboard."""
    manager = get_manager()

    if not manager.is_car_connected:
        display_console.error("Not connected to vehicle")
        raise typer.Exit(1)

    # Determine which PIDs to monitor
    if pids:
        pid_list = [p.strip().upper() for p in pids.split(",")]
    elif preset and preset in PID_PRESETS:
        pid_list = PID_PRESETS[preset]
    else:
        pid_list = PID_PRESETS["engine"]  # Default preset

    display_console.info(f"Starting monitor with PIDs: {', '.join(pid_list)}")
    display_console.info("Press Ctrl+C to stop\n")

    collector = LiveDataCollector(manager, pids=pid_list, interval_ms=interval)
    live_display = LiveDisplay()

    # Get vehicle info for header
    try:
        vin_collector = VINCollector(manager)
        vehicle = vin_collector.get_vehicle_info()
        vehicle_str = f"{vehicle.manufacturer} {vehicle.model_year}" if vehicle else None
    except:
        vehicle_str = None

    try:
        live_display.start_monitoring(
            get_values=collector.get_latest,
            refresh_rate=interval / 1000,
            vehicle_info=vehicle_str,
            connection_info=manager.protocol,
            show_gauges=not no_gauges,
        )
    except KeyboardInterrupt:
        pass

    display_console.newline()
    display_console.info("Monitoring stopped")


# ============ DTC Commands ============

@dtc_app.command("read")
def dtc_read(
    stored: bool = typer.Option(True, "--stored/--no-stored", help="Read stored codes"),
    pending: bool = typer.Option(True, "--pending/--no-pending", help="Read pending codes"),
    permanent: bool = typer.Option(True, "--permanent/--no-permanent", help="Read permanent codes"),
):
    """Read diagnostic trouble codes."""
    manager = get_manager()

    if not manager.is_car_connected:
        display_console.error("Not connected to vehicle")
        raise typer.Exit(1)

    display_console.header("Diagnostic Trouble Codes")

    collector = DTCCollector(manager)
    result = collector.collect()

    # Show summary
    _table_display.show(_table_display.dtc_summary_table(result))

    # Show stored codes
    if stored and result.stored_codes:
        display_console.subheader("Stored Codes")
        _table_display.show(_table_display.dtc_table(result.stored_codes, "Stored DTCs"))

    # Show pending codes
    if pending and result.pending_codes:
        display_console.subheader("Pending Codes")
        _table_display.show(_table_display.dtc_table(result.pending_codes, "Pending DTCs"))

    # Show permanent codes
    if permanent and result.permanent_codes:
        display_console.subheader("Permanent Codes")
        _table_display.show(_table_display.dtc_table(result.permanent_codes, "Permanent DTCs"))

    if result.total_codes == 0:
        display_console.success("No diagnostic trouble codes found!")


@dtc_app.command("clear")
def dtc_clear(
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Clear diagnostic trouble codes."""
    manager = get_manager()

    if not manager.is_car_connected:
        display_console.error("Not connected to vehicle")
        raise typer.Exit(1)

    if not force:
        display_console.warning("This will clear all DTCs and turn off the check engine light.")
        display_console.warning("Note: Permanent codes cannot be cleared without fixing the issue.")
        if not display_console.confirm("Are you sure you want to clear DTCs?"):
            display_console.info("Cancelled")
            return

    collector = DTCCollector(manager)

    if collector.clear_dtcs(force=True):
        display_console.success("DTCs cleared successfully")
        display_console.info("Note: MIL may take a drive cycle to turn off")
    else:
        display_console.error("Failed to clear DTCs")


@dtc_app.command("search")
def dtc_search(
    query: str = typer.Argument(..., help="Search query"),
):
    """Search DTC codes by description."""
    decoder = DTCDecoder()
    results = decoder.search(query)

    if results:
        display_console.header(f"Search Results for '{query}'")
        _table_display.show(_table_display.dtc_table(results, f"Found {len(results)} codes"))
    else:
        display_console.warning(f"No codes found matching '{query}'")


# ============ PID Commands ============

@pid_app.command("list")
def pid_list(
    supported_only: bool = typer.Option(False, "--supported", "-s", help="Show only supported PIDs"),
):
    """List available PIDs."""
    manager = get_manager()

    collector = PIDCollector(manager)
    pids = collector.list_all_pids()

    if supported_only:
        pids = [p for p in pids if p.is_supported]

    display_console.header("Available PIDs")
    _table_display.show(_table_display.pid_info_table(pids))
    display_console.info(f"Total: {len(pids)} PIDs")


@pid_app.command("read")
def pid_read(
    pid_name: str = typer.Argument(..., help="PID name to read (e.g., RPM, SPEED)"),
    continuous: bool = typer.Option(False, "--continuous", "-c", help="Continuous reading"),
    interval: int = typer.Option(500, "--interval", "-i", help="Interval in ms for continuous mode"),
):
    """Read a specific PID value."""
    manager = get_manager()

    if not manager.is_car_connected:
        display_console.error("Not connected to vehicle")
        raise typer.Exit(1)

    collector = PIDCollector(manager)
    pid_name = pid_name.upper()

    if continuous:
        display_console.info(f"Reading {pid_name} continuously. Press Ctrl+C to stop.\n")
        try:
            while True:
                value = collector.read_pid(pid_name)
                if value and value.is_valid:
                    display_console.print(f"\r{value.name}: {value.formatted_value}    ", end="")
                else:
                    display_console.print(f"\r{pid_name}: N/A    ", end="")
                import time
                time.sleep(interval / 1000)
        except KeyboardInterrupt:
            display_console.newline()
    else:
        value = collector.read_pid(pid_name)
        if value and value.is_valid:
            display_console.print_pid(value.name, value.value, value.unit)
        else:
            display_console.error(f"Could not read {pid_name}: {value.error_message if value else 'Unknown error'}")


@pid_app.command("search")
def pid_search(
    query: str = typer.Argument(..., help="Search query"),
):
    """Search PIDs by name or description."""
    manager = get_manager()
    collector = PIDCollector(manager)
    results = collector.search_pids(query)

    if results:
        display_console.header(f"PIDs matching '{query}'")
        _table_display.show(_table_display.pid_info_table(results))
    else:
        display_console.warning(f"No PIDs found matching '{query}'")


# ============ Log Commands ============

@log_app.command("start")
def log_start(
    pids: Optional[str] = typer.Option(None, "--pids", "-p", help="Comma-separated PIDs to log"),
    preset: Optional[str] = typer.Option("performance", "--preset", help="PID preset"),
    format: str = typer.Option("json", "--format", "-f", help="Output format (json, csv)"),
    interval: int = typer.Option(500, "--interval", "-i", help="Logging interval in ms"),
):
    """Start data logging session."""
    manager = get_manager()

    if not manager.is_car_connected:
        display_console.error("Not connected to vehicle")
        raise typer.Exit(1)

    # Determine PIDs
    if pids:
        pid_list = [p.strip().upper() for p in pids.split(",")]
    elif preset in PID_PRESETS:
        pid_list = PID_PRESETS[preset]
    else:
        pid_list = PID_PRESETS["performance"]

    logger = SessionLogger(format=format)

    # Get vehicle info
    try:
        vin_collector = VINCollector(manager)
        vehicle_info = vin_collector.get_vehicle_info()
    except:
        vehicle_info = None

    session = logger.start_session(vehicle_info=vehicle_info, pids=pid_list)

    display_console.success(f"Started logging session: {session.session_id}")
    display_console.info(f"Logging PIDs: {', '.join(pid_list)}")
    display_console.info("Press Ctrl+C to stop logging\n")

    collector = LiveDataCollector(manager, pids=pid_list, interval_ms=interval)

    try:
        collector.start_streaming()
        while True:
            samples = collector.get_buffered_samples(max_samples=10)
            for sample in samples:
                logger.log_sample(sample)

            import time
            time.sleep(0.5)

            # Show progress
            stats = collector.get_statistics()
            display_console.print(
                f"\rSamples: {stats['sample_count']} | Rate: {stats['samples_per_second']:.1f}/s    ",
                end=""
            )

    except KeyboardInterrupt:
        pass
    finally:
        collector.stop_streaming()
        filepath = logger.end_session()

    display_console.newline()
    display_console.success(f"Logging stopped. Data saved to: {filepath}")


@log_app.command("stop")
def log_stop():
    """Stop current logging session."""
    display_console.info("Use Ctrl+C to stop an active logging session")


# ============ History Commands ============

@history_app.command("list")
def history_list(
    limit: int = typer.Option(10, "--limit", "-n", help="Number of sessions to show"),
):
    """List logged sessions."""
    hist_manager = HistoryManager()
    sessions = hist_manager.list_sessions(limit=limit)

    if sessions:
        display_console.header("Diagnostic Sessions")
        _table_display.show(_table_display.session_table(sessions))
    else:
        display_console.info("No logged sessions found")


@history_app.command("show")
def history_show(
    session_id: str = typer.Argument(..., help="Session ID to show"),
):
    """Show details of a logged session."""
    hist_manager = HistoryManager()
    session = hist_manager.load_session(session_id)

    if session:
        display_console.header(f"Session {session.session_id}")
        display_console.print(f"Start: {session.start_time}")
        display_console.print(f"Samples: {session.sample_count}")

        if session.vehicle_info:
            display_console.subheader("Vehicle")
            _table_display.show(_table_display.vehicle_info_table(session.vehicle_info))

        if session.dtc_result:
            display_console.subheader("DTCs")
            _table_display.show(_table_display.dtc_summary_table(session.dtc_result))
    else:
        display_console.error(f"Session not found: {session_id}")


@history_app.command("export")
def history_export(
    session_id: str = typer.Argument(..., help="Session ID to export"),
    format: str = typer.Option("csv", "--format", "-f", help="Export format (csv, json)"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file path"),
):
    """Export a session to file."""
    hist_manager = HistoryManager()

    filepath = hist_manager.export_session(session_id, format=format, output_path=output)

    if filepath:
        display_console.success(f"Exported to: {filepath}")
    else:
        display_console.error(f"Failed to export session: {session_id}")


# ============ Analyze Commands ============

@analyze_app.command("performance")
def analyze_performance(
    file: Optional[str] = typer.Option(None, "--file", "-f", help="Analyze logged session file"),
):
    """Analyze performance data."""
    manager = get_manager()

    from .analysis.performance import PerformanceAnalyzer

    analyzer = PerformanceAnalyzer()

    if file:
        # Analyze from file
        hist_manager = HistoryManager()
        session = hist_manager.load_session_from_file(file)
        if not session:
            display_console.error(f"Could not load session from: {file}")
            raise typer.Exit(1)
    else:
        # Analyze live data
        if not manager.is_car_connected:
            display_console.error("Not connected. Use --file to analyze logged data.")
            raise typer.Exit(1)

        from .models.session import DiagnosticSession
        collector = LiveDataCollector(manager)

        display_console.info("Collecting data for analysis (10 seconds)...")
        collector.start_streaming()

        import time
        time.sleep(10)

        collector.stop_streaming()
        samples = collector.get_buffered_samples(max_samples=1000)

        session = DiagnosticSession()
        session.pid_samples = samples

    result = analyzer.analyze(session)
    display_console.header("Performance Analysis")
    _table_display.show(_table_display.analysis_table(result))

    if result.findings:
        display_console.subheader("Recommendations")
        for finding in result.findings:
            for rec in finding.recommendations:
                display_console.print(f"  - {rec}")


@analyze_app.command("fuel")
def analyze_fuel(
    file: Optional[str] = typer.Option(None, "--file", "-f", help="Analyze logged session file"),
):
    """Analyze fuel economy."""
    manager = get_manager()

    from .analysis.fuel import FuelEconomyAnalyzer

    analyzer = FuelEconomyAnalyzer()

    if file:
        hist_manager = HistoryManager()
        session = hist_manager.load_session_from_file(file)
        if not session:
            display_console.error(f"Could not load session from: {file}")
            raise typer.Exit(1)
    else:
        if not manager.is_car_connected:
            display_console.error("Not connected. Use --file to analyze logged data.")
            raise typer.Exit(1)

        from .models.session import DiagnosticSession
        collector = LiveDataCollector(manager, pids=["RPM", "SPEED", "MAF", "ENGINE_LOAD"])

        display_console.info("Collecting fuel data (15 seconds)...")
        collector.start_streaming()

        import time
        time.sleep(15)

        collector.stop_streaming()
        samples = collector.get_buffered_samples(max_samples=1000)

        session = DiagnosticSession()
        session.pid_samples = samples

    result = analyzer.analyze(session)
    display_console.header("Fuel Economy Analysis")
    _table_display.show(_table_display.analysis_table(result))

    if "average_mpg" in result.metrics:
        display_console.print(f"\n  Average MPG: {result.metrics['average_mpg']:.1f}")


@analyze_app.command("faults")
def analyze_faults(
    file: Optional[str] = typer.Option(None, "--file", "-f", help="Analyze logged session file"),
):
    """Detect potential faults."""
    manager = get_manager()

    from .analysis.faults import FaultDetector

    detector = FaultDetector()

    if file:
        hist_manager = HistoryManager()
        session = hist_manager.load_session_from_file(file)
        if not session:
            display_console.error(f"Could not load session from: {file}")
            raise typer.Exit(1)
    else:
        if not manager.is_car_connected:
            display_console.error("Not connected. Use --file to analyze logged data.")
            raise typer.Exit(1)

        # Collect comprehensive data
        from .models.session import DiagnosticSession

        session = DiagnosticSession()

        # Get DTCs
        dtc_collector = DTCCollector(manager)
        session.dtc_result = dtc_collector.collect()

        # Get sensor data
        collector = LiveDataCollector(manager)
        display_console.info("Collecting sensor data (10 seconds)...")
        collector.start_streaming()

        import time
        time.sleep(10)

        collector.stop_streaming()
        session.pid_samples = collector.get_buffered_samples(max_samples=1000)

    result = detector.analyze(session)
    display_console.header("Fault Analysis")
    _table_display.show(_table_display.analysis_table(result))


@analyze_app.command("all")
def analyze_all(
    file: Optional[str] = typer.Option(None, "--file", "-f", help="Analyze logged session file"),
):
    """Run all analyzers."""
    display_console.info("Running all analyzers...")
    analyze_performance(file)
    analyze_fuel(file)
    analyze_faults(file)


# ============ Version Command ============

@app.command()
def version():
    """Show version information."""
    from . import __version__
    display_console.print(f"OBD Toolkit v{__version__}")


if __name__ == "__main__":
    app()
