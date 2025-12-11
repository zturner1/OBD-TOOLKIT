"""Connection management for OBD2 adapters."""

from .manager import ConnectionManager
from .adapter import AdapterDetector, AdapterInfo

__all__ = ["ConnectionManager", "AdapterDetector", "AdapterInfo"]
