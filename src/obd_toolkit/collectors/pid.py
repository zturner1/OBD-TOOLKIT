"""PID (Parameter ID) collector."""

from typing import List, Optional, Dict, Set
import logging

import obd

from .base import BaseCollector
from ..models.pid import PIDValue, PIDInfo, PIDSnapshot, COMMON_PIDS

logger = logging.getLogger(__name__)


class PIDCollector(BaseCollector):
    """Collects PID data from vehicle."""

    def __init__(self, connection_manager):
        super().__init__(connection_manager)
        self._supported_pids: Optional[Set[str]] = None

    def collect(self) -> PIDSnapshot:
        """Collect all supported PIDs."""
        self._ensure_connected()

        values = {}
        for pid_name in self.get_supported_pids():
            value = self.read_pid(pid_name)
            if value:
                values[pid_name] = value

        return PIDSnapshot(values=values)

    def is_supported(self) -> bool:
        """Check if PID reading is supported."""
        return self.is_connected and len(self.get_supported_pids()) > 0

    def read_pid(self, pid_name: str) -> Optional[PIDValue]:
        """
        Read a single PID value.

        Args:
            pid_name: Name of the PID (e.g., 'RPM', 'SPEED')

        Returns:
            PIDValue or None if not available
        """
        self._ensure_connected()

        # Get command from obd library
        cmd = obd.commands.get(pid_name)

        if cmd is None:
            logger.warning(f"Unknown PID: {pid_name}")
            return PIDValue(
                pid=pid_name,
                name=pid_name,
                is_valid=False,
                error_message=f"Unknown PID: {pid_name}"
            )

        try:
            response = self.connection.query(cmd)

            if response.is_null():
                return PIDValue(
                    pid=pid_name,
                    name=cmd.name,
                    is_valid=False,
                    error_message="No response from vehicle"
                )

            # Extract value and unit
            value = response.value
            unit = ""

            # Handle pint quantities (python-OBD uses pint for units)
            if hasattr(value, 'magnitude'):
                numeric_value = value.magnitude
                unit = str(value.units) if hasattr(value, 'units') else ""
            elif isinstance(value, (int, float)):
                numeric_value = value
            else:
                numeric_value = value

            return PIDValue(
                pid=pid_name,
                name=cmd.name,
                value=numeric_value,
                unit=unit,
                is_valid=True,
            )

        except Exception as e:
            logger.error(f"Error reading PID {pid_name}: {e}")
            return PIDValue(
                pid=pid_name,
                name=pid_name,
                is_valid=False,
                error_message=str(e)
            )

    def read_multiple(self, pid_names: List[str]) -> Dict[str, PIDValue]:
        """
        Read multiple PIDs.

        Args:
            pid_names: List of PID names to read

        Returns:
            Dictionary of pid_name -> PIDValue
        """
        results = {}
        for pid_name in pid_names:
            value = self.read_pid(pid_name)
            if value:
                results[pid_name] = value
        return results

    def get_supported_pids(self) -> List[str]:
        """Get list of PIDs supported by the vehicle."""
        if self._supported_pids is not None:
            return list(self._supported_pids)

        if not self.connection:
            return []

        # Get supported commands from connection
        supported = set()
        for cmd in self.connection.supported_commands:
            if cmd.mode == 1:  # Mode 01 = Live data
                supported.add(cmd.name)

        self._supported_pids = supported
        return list(supported)

    def refresh_supported_pids(self) -> List[str]:
        """Refresh the list of supported PIDs."""
        self._supported_pids = None
        return self.get_supported_pids()

    def get_pid_info(self, pid_name: str) -> Optional[PIDInfo]:
        """
        Get information about a PID.

        Args:
            pid_name: Name of the PID

        Returns:
            PIDInfo or None if not found
        """
        # Check our common PIDs first
        if pid_name in COMMON_PIDS:
            info = COMMON_PIDS[pid_name].model_copy()
            info.is_supported = pid_name in self.get_supported_pids()
            return info

        # Try to get from obd library
        cmd = obd.commands.get(pid_name)
        if cmd:
            return PIDInfo(
                pid=pid_name,
                name=cmd.name,
                description=cmd.desc,
                is_supported=pid_name in self.get_supported_pids()
            )

        return None

    def list_all_pids(self) -> List[PIDInfo]:
        """List all known PIDs with support status."""
        supported = set(self.get_supported_pids())
        pids = []

        # Add common PIDs
        for pid_name, info in COMMON_PIDS.items():
            pid_info = info.model_copy()
            pid_info.is_supported = pid_name in supported
            pids.append(pid_info)

        # Add any additional supported PIDs not in common list
        for pid_name in supported:
            if pid_name not in COMMON_PIDS:
                cmd = obd.commands.get(pid_name)
                if cmd:
                    pids.append(PIDInfo(
                        pid=pid_name,
                        name=cmd.name,
                        description=cmd.desc,
                        is_supported=True
                    ))

        return pids

    def search_pids(self, query: str) -> List[PIDInfo]:
        """
        Search PIDs by name or description.

        Args:
            query: Search query string

        Returns:
            List of matching PIDs
        """
        query = query.lower()
        results = []

        for pid_info in self.list_all_pids():
            if (query in pid_info.pid.lower() or
                query in pid_info.name.lower() or
                query in pid_info.description.lower()):
                results.append(pid_info)

        return results
