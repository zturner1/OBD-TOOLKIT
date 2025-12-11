"""Base collector class for OBD data collection."""

from abc import ABC, abstractmethod
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..connection.manager import ConnectionManager


class BaseCollector(ABC):
    """Abstract base class for all data collectors."""

    def __init__(self, connection_manager: "ConnectionManager"):
        """
        Initialize collector with connection manager.

        Args:
            connection_manager: The connection manager to use for queries
        """
        self._conn_manager = connection_manager

    @property
    def connection(self):
        """Get the underlying OBD connection."""
        return self._conn_manager.connection

    @property
    def is_connected(self) -> bool:
        """Check if connected to vehicle."""
        return self._conn_manager.is_car_connected

    def _ensure_connected(self) -> None:
        """Raise exception if not connected."""
        if not self.is_connected:
            raise ConnectionError("Not connected to vehicle. Please connect first.")

    @abstractmethod
    def collect(self) -> Any:
        """
        Collect data from the vehicle.

        Returns:
            Collected data (type depends on collector implementation)
        """
        pass

    @abstractmethod
    def is_supported(self) -> bool:
        """
        Check if this type of collection is supported by the vehicle.

        Returns:
            True if supported, False otherwise
        """
        pass
