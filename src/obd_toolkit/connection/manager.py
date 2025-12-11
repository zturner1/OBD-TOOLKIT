"""Connection manager for OBD2 adapters."""

import logging
from typing import Optional, List, Callable
from dataclasses import dataclass
from enum import Enum

import obd
from obd import OBDStatus

from .adapter import AdapterDetector, AdapterInfo, AdapterType

logger = logging.getLogger(__name__)


class ConnectionState(str, Enum):
    """Connection state enumeration."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    CAR_CONNECTED = "car_connected"
    ERROR = "error"


@dataclass
class ConnectionResult:
    """Result of a connection attempt."""
    success: bool
    state: ConnectionState
    message: str
    adapter_info: Optional[AdapterInfo] = None
    protocol: str = ""
    error: Optional[str] = None


class ConnectionManager:
    """Manages OBD2 adapter connections."""

    def __init__(self, auto_connect: bool = False):
        self._connection: Optional[obd.OBD] = None
        self._adapter_info: Optional[AdapterInfo] = None
        self._state: ConnectionState = ConnectionState.DISCONNECTED
        self._protocol: str = ""
        self._on_state_change: Optional[Callable[[ConnectionState], None]] = None

        if auto_connect:
            self.connect()

    @property
    def connection(self) -> Optional[obd.OBD]:
        """Get the underlying OBD connection."""
        return self._connection

    @property
    def is_connected(self) -> bool:
        """Check if connected to an adapter."""
        if not self._connection:
            return False
        return self._connection.status() != OBDStatus.NOT_CONNECTED

    @property
    def is_car_connected(self) -> bool:
        """Check if connected to a vehicle (not just adapter)."""
        if not self._connection:
            return False
        return self._connection.status() == OBDStatus.CAR_CONNECTED

    @property
    def state(self) -> ConnectionState:
        """Get current connection state."""
        return self._state

    @property
    def adapter_info(self) -> Optional[AdapterInfo]:
        """Get info about connected adapter."""
        return self._adapter_info

    @property
    def protocol(self) -> str:
        """Get the OBD protocol in use."""
        return self._protocol

    def on_state_change(self, callback: Callable[[ConnectionState], None]) -> None:
        """Register callback for state changes."""
        self._on_state_change = callback

    def _set_state(self, state: ConnectionState) -> None:
        """Update state and notify callbacks."""
        self._state = state
        if self._on_state_change:
            try:
                self._on_state_change(state)
            except Exception as e:
                logger.warning(f"State change callback error: {e}")

    def connect(
        self,
        port: Optional[str] = None,
        baudrate: int = 38400,
        protocol: Optional[str] = None,
        fast: bool = True,
        timeout: float = 3.0,
    ) -> ConnectionResult:
        """
        Connect to an OBD2 adapter.

        Args:
            port: Serial port name (auto-detect if None)
            baudrate: Baud rate for serial connection
            protocol: Force specific OBD protocol (auto-detect if None)
            fast: Use fast OBD queries
            timeout: Connection timeout in seconds

        Returns:
            ConnectionResult with success status and details
        """
        self._set_state(ConnectionState.CONNECTING)

        # Auto-detect port if not specified
        if port is None:
            adapter = AdapterDetector.find_best_adapter()
            if adapter:
                port = adapter.port
                self._adapter_info = adapter
                logger.info(f"Auto-detected adapter: {adapter}")
            else:
                self._set_state(ConnectionState.ERROR)
                return ConnectionResult(
                    success=False,
                    state=ConnectionState.ERROR,
                    message="No OBD2 adapter found",
                    error="Could not auto-detect an OBD2 adapter. Please specify a port.",
                )
        else:
            self._adapter_info = AdapterDetector.get_port_by_name(port)

        # Close existing connection if any
        if self._connection:
            self.disconnect()

        try:
            logger.info(f"Connecting to {port} at {baudrate} baud...")

            self._connection = obd.OBD(
                portstr=port,
                baudrate=baudrate,
                protocol=protocol,
                fast=fast,
                timeout=timeout,
            )

            status = self._connection.status()

            if status == OBDStatus.CAR_CONNECTED:
                self._set_state(ConnectionState.CAR_CONNECTED)
                self._protocol = self._connection.protocol_name() or "Unknown"

                return ConnectionResult(
                    success=True,
                    state=ConnectionState.CAR_CONNECTED,
                    message=f"Connected to vehicle via {self._protocol}",
                    adapter_info=self._adapter_info,
                    protocol=self._protocol,
                )

            elif status == OBDStatus.OBD_CONNECTED:
                self._set_state(ConnectionState.CONNECTED)
                self._protocol = self._connection.protocol_name() or "Unknown"

                return ConnectionResult(
                    success=True,
                    state=ConnectionState.CONNECTED,
                    message="Connected to adapter (ignition may be off)",
                    adapter_info=self._adapter_info,
                    protocol=self._protocol,
                )

            else:
                self._set_state(ConnectionState.ERROR)
                return ConnectionResult(
                    success=False,
                    state=ConnectionState.ERROR,
                    message="Failed to establish connection",
                    error=f"Connection status: {status}",
                )

        except Exception as e:
            logger.error(f"Connection error: {e}")
            self._set_state(ConnectionState.ERROR)

            return ConnectionResult(
                success=False,
                state=ConnectionState.ERROR,
                message="Connection failed",
                error=str(e),
            )

    def disconnect(self) -> None:
        """Disconnect from the OBD2 adapter."""
        if self._connection:
            try:
                self._connection.close()
            except Exception as e:
                logger.warning(f"Error closing connection: {e}")
            finally:
                self._connection = None

        self._adapter_info = None
        self._protocol = ""
        self._set_state(ConnectionState.DISCONNECTED)
        logger.info("Disconnected from OBD2 adapter")

    def reconnect(self) -> ConnectionResult:
        """Attempt to reconnect using previous settings."""
        port = self._adapter_info.port if self._adapter_info else None
        self.disconnect()
        return self.connect(port=port)

    def get_supported_commands(self) -> List[str]:
        """Get list of supported OBD commands."""
        if not self._connection:
            return []

        return [cmd.name for cmd in self._connection.supported_commands]

    def get_supported_pids(self) -> List[str]:
        """Get list of supported PIDs (Mode 01)."""
        if not self._connection:
            return []

        mode01_cmds = [
            cmd.name for cmd in self._connection.supported_commands
            if cmd.mode == 1
        ]
        return mode01_cmds

    def query(self, command) -> Optional[obd.OBDResponse]:
        """
        Execute an OBD command.

        Args:
            command: OBD command (string name or OBDCommand object)

        Returns:
            OBDResponse or None if failed
        """
        if not self._connection:
            logger.warning("Cannot query: not connected")
            return None

        if isinstance(command, str):
            cmd = obd.commands.get(command)
            if cmd is None:
                logger.warning(f"Unknown command: {command}")
                return None
        else:
            cmd = command

        try:
            response = self._connection.query(cmd)
            return response
        except Exception as e:
            logger.error(f"Query error for {command}: {e}")
            return None

    def get_status_info(self) -> dict:
        """Get detailed status information."""
        status = {
            "state": self._state.value,
            "is_connected": self.is_connected,
            "is_car_connected": self.is_car_connected,
            "protocol": self._protocol,
            "adapter": None,
            "supported_commands_count": 0,
        }

        if self._adapter_info:
            status["adapter"] = {
                "port": self._adapter_info.port,
                "type": self._adapter_info.adapter_type.value,
                "description": self._adapter_info.description,
            }

        if self._connection:
            status["supported_commands_count"] = len(self._connection.supported_commands)

        return status

    def __enter__(self):
        """Context manager entry."""
        if not self.is_connected:
            self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
        return False


# Global connection manager instance for convenience
_global_manager: Optional[ConnectionManager] = None


def get_connection_manager() -> ConnectionManager:
    """Get or create the global connection manager."""
    global _global_manager
    if _global_manager is None:
        _global_manager = ConnectionManager()
    return _global_manager


def reset_connection_manager() -> None:
    """Reset the global connection manager."""
    global _global_manager
    if _global_manager:
        _global_manager.disconnect()
    _global_manager = None
