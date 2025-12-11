"""Live data collector for real-time monitoring."""

import time
import logging
from typing import List, Dict, Optional, Callable
from threading import Thread, Event
from queue import Queue, Empty
from datetime import datetime

from .base import BaseCollector
from .pid import PIDCollector
from ..models.pid import PIDValue, PIDSnapshot
from ..models.session import PIDSample

logger = logging.getLogger(__name__)


class LiveDataCollector(BaseCollector):
    """Collects real-time PID data with continuous streaming support."""

    def __init__(
        self,
        connection_manager,
        pids: Optional[List[str]] = None,
        interval_ms: int = 250
    ):
        """
        Initialize live data collector.

        Args:
            connection_manager: Connection manager instance
            pids: List of PIDs to monitor (None = use defaults)
            interval_ms: Polling interval in milliseconds
        """
        super().__init__(connection_manager)
        self._pid_collector = PIDCollector(connection_manager)

        # Default PIDs if none specified
        self._pids = pids or ["RPM", "SPEED", "COOLANT_TEMP", "ENGINE_LOAD", "THROTTLE_POS"]
        self._interval = interval_ms / 1000.0

        # Streaming state
        self._running = False
        self._thread: Optional[Thread] = None
        self._stop_event = Event()

        # Data storage
        self._buffer: Queue[PIDSample] = Queue(maxsize=1000)
        self._latest_values: Dict[str, PIDValue] = {}
        self._callbacks: List[Callable[[PIDSample], None]] = []

        # Statistics
        self._sample_count = 0
        self._error_count = 0
        self._start_time: Optional[datetime] = None

    def collect(self) -> PIDSnapshot:
        """Collect single snapshot of all monitored PIDs."""
        self._ensure_connected()
        return PIDSnapshot(values=self.get_latest())

    def is_supported(self) -> bool:
        """Check if live monitoring is supported."""
        return self._pid_collector.is_supported()

    @property
    def pids(self) -> List[str]:
        """Get list of monitored PIDs."""
        return self._pids.copy()

    @pids.setter
    def pids(self, value: List[str]) -> None:
        """Set PIDs to monitor."""
        self._pids = value

    @property
    def is_streaming(self) -> bool:
        """Check if currently streaming data."""
        return self._running

    @property
    def sample_count(self) -> int:
        """Get number of samples collected."""
        return self._sample_count

    @property
    def samples_per_second(self) -> float:
        """Calculate current sampling rate."""
        if not self._start_time or self._sample_count == 0:
            return 0.0
        elapsed = (datetime.now() - self._start_time).total_seconds()
        return self._sample_count / elapsed if elapsed > 0 else 0.0

    def start_streaming(self) -> None:
        """Start background data collection thread."""
        if self._running:
            logger.warning("Streaming already active")
            return

        self._ensure_connected()
        self._stop_event.clear()
        self._running = True
        self._sample_count = 0
        self._error_count = 0
        self._start_time = datetime.now()

        self._thread = Thread(target=self._stream_loop, daemon=True)
        self._thread.start()
        logger.info(f"Started streaming {len(self._pids)} PIDs at {1/self._interval:.1f} Hz")

    def stop_streaming(self) -> None:
        """Stop data collection."""
        if not self._running:
            return

        self._stop_event.set()
        self._running = False

        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

        logger.info(f"Stopped streaming. Collected {self._sample_count} samples.")

    def _stream_loop(self) -> None:
        """Background thread loop for continuous data collection."""
        while not self._stop_event.is_set():
            try:
                # Collect all PIDs
                values = {}
                for pid in self._pids:
                    try:
                        value = self._pid_collector.read_pid(pid)
                        if value:
                            values[pid] = value
                    except Exception as e:
                        logger.debug(f"Error reading {pid}: {e}")
                        self._error_count += 1

                # Update latest values
                self._latest_values.update(values)

                # Create sample
                if values:
                    snapshot = PIDSnapshot(values=values)
                    sample = PIDSample.from_snapshot(snapshot)

                    # Add to buffer (non-blocking)
                    try:
                        self._buffer.put_nowait(sample)
                    except:
                        # Buffer full, discard oldest
                        try:
                            self._buffer.get_nowait()
                            self._buffer.put_nowait(sample)
                        except:
                            pass

                    # Notify callbacks
                    for callback in self._callbacks:
                        try:
                            callback(sample)
                        except Exception as e:
                            logger.error(f"Callback error: {e}")

                    self._sample_count += 1

                # Wait for next interval
                time.sleep(self._interval)

            except Exception as e:
                logger.error(f"Stream loop error: {e}")
                self._error_count += 1
                time.sleep(0.5)

    def get_latest(self) -> Dict[str, PIDValue]:
        """Get most recent values for all monitored PIDs."""
        if self._running:
            return self._latest_values.copy()

        # If not streaming, do a fresh read
        values = {}
        for pid in self._pids:
            value = self._pid_collector.read_pid(pid)
            if value:
                values[pid] = value
        self._latest_values = values
        return values.copy()

    def get_buffered_samples(self, max_samples: int = 100) -> List[PIDSample]:
        """
        Get samples from buffer.

        Args:
            max_samples: Maximum number of samples to return

        Returns:
            List of samples (oldest first)
        """
        samples = []
        while len(samples) < max_samples:
            try:
                sample = self._buffer.get_nowait()
                samples.append(sample)
            except Empty:
                break
        return samples

    def clear_buffer(self) -> None:
        """Clear the sample buffer."""
        while not self._buffer.empty():
            try:
                self._buffer.get_nowait()
            except Empty:
                break

    def subscribe(self, callback: Callable[[PIDSample], None]) -> None:
        """
        Subscribe to real-time updates.

        Args:
            callback: Function called with each new sample
        """
        if callback not in self._callbacks:
            self._callbacks.append(callback)

    def unsubscribe(self, callback: Callable[[PIDSample], None]) -> None:
        """Unsubscribe from updates."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def set_interval(self, interval_ms: int) -> None:
        """Set polling interval in milliseconds."""
        self._interval = interval_ms / 1000.0

    def add_pid(self, pid: str) -> None:
        """Add a PID to monitor."""
        if pid not in self._pids:
            self._pids.append(pid)

    def remove_pid(self, pid: str) -> None:
        """Remove a PID from monitoring."""
        if pid in self._pids:
            self._pids.remove(pid)

    def get_statistics(self) -> Dict:
        """Get collection statistics."""
        return {
            "is_streaming": self._running,
            "sample_count": self._sample_count,
            "error_count": self._error_count,
            "samples_per_second": self.samples_per_second,
            "buffer_size": self._buffer.qsize(),
            "monitored_pids": len(self._pids),
            "interval_ms": self._interval * 1000,
        }

    def __enter__(self):
        """Context manager entry - start streaming."""
        self.start_streaming()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - stop streaming."""
        self.stop_streaming()
        return False
