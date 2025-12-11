"""Session logging for OBD data."""

import json
import csv
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, List

from ..models.session import DiagnosticSession, PIDSample
from ..models.vehicle import VehicleInfo

logger = logging.getLogger(__name__)


class SessionLogger:
    """Logs diagnostic session data to files."""

    DEFAULT_DATA_DIR = Path.home() / ".obd-toolkit" / "logs"

    def __init__(
        self,
        data_dir: Optional[Path] = None,
        format: str = "json"
    ):
        """
        Initialize session logger.

        Args:
            data_dir: Directory to store log files
            format: Output format ('json' or 'csv')
        """
        self._data_dir = data_dir or self.DEFAULT_DATA_DIR
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._format = format.lower()

        self._current_session: Optional[DiagnosticSession] = None
        self._current_file: Optional[Path] = None
        self._csv_writer = None
        self._csv_file = None
        self._sample_count = 0

    @property
    def data_dir(self) -> Path:
        """Get data directory path."""
        return self._data_dir

    @property
    def current_session(self) -> Optional[DiagnosticSession]:
        """Get current session."""
        return self._current_session

    @property
    def is_logging(self) -> bool:
        """Check if a session is active."""
        return self._current_session is not None

    def start_session(
        self,
        vehicle_info: Optional[VehicleInfo] = None,
        pids: Optional[List[str]] = None,
        notes: str = ""
    ) -> DiagnosticSession:
        """
        Start a new logging session.

        Args:
            vehicle_info: Vehicle information
            pids: List of PIDs being logged
            notes: Session notes

        Returns:
            New DiagnosticSession
        """
        if self._current_session:
            self.end_session()

        self._current_session = DiagnosticSession(
            vehicle_info=vehicle_info,
            notes=notes,
        )

        # Create file path
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"session_{self._current_session.session_id}_{timestamp}.{self._format}"
        self._current_file = self._data_dir / filename

        self._sample_count = 0

        if self._format == "csv":
            self._init_csv(pids or [])

        logger.info(f"Started logging session {self._current_session.session_id}")
        return self._current_session

    def _init_csv(self, pids: List[str]) -> None:
        """Initialize CSV file with headers."""
        self._csv_file = open(self._current_file, 'w', newline='')
        self._csv_writer = csv.writer(self._csv_file)

        # Write header
        headers = ["timestamp"] + pids
        self._csv_writer.writerow(headers)
        self._csv_pids = pids

    def log_sample(self, sample: PIDSample) -> None:
        """
        Log a PID sample to the session.

        Args:
            sample: PID sample to log
        """
        if not self._current_session:
            return

        self._current_session.add_sample(sample)
        self._sample_count += 1

        # Write to CSV immediately if using CSV format
        if self._format == "csv" and self._csv_writer:
            row = [sample.timestamp.isoformat()]
            for pid in self._csv_pids:
                row.append(sample.values.get(pid, ""))
            self._csv_writer.writerow(row)

            # Flush periodically
            if self._sample_count % 10 == 0:
                self._csv_file.flush()

    def log_dtc_result(self, dtc_result) -> None:
        """Log DTC reading result."""
        if self._current_session:
            self._current_session.dtc_result = dtc_result

    def log_analysis_result(self, result) -> None:
        """Log analysis result."""
        if self._current_session:
            self._current_session.add_analysis(result)

    def end_session(self) -> Optional[Path]:
        """
        End the current session and save to file.

        Returns:
            Path to saved file or None
        """
        if not self._current_session:
            return None

        self._current_session.end_session()

        if self._format == "csv":
            # Close CSV file
            if self._csv_file:
                self._csv_file.close()
                self._csv_file = None
                self._csv_writer = None
        else:
            # Write JSON
            self._write_json()

        filepath = self._current_file
        logger.info(f"Ended session {self._current_session.session_id}, saved to {filepath}")

        self._current_session = None
        self._current_file = None

        return filepath

    def _write_json(self) -> None:
        """Write session data to JSON file."""
        if not self._current_session or not self._current_file:
            return

        data = self._current_session.to_dict_for_export()

        with open(self._current_file, 'w') as f:
            json.dump(data, f, indent=2, default=str)

    def add_note(self, note: str) -> None:
        """Add a note to the current session."""
        if self._current_session:
            if self._current_session.notes:
                self._current_session.notes += f"\n{note}"
            else:
                self._current_session.notes = note

    def add_tag(self, tag: str) -> None:
        """Add a tag to the current session."""
        if self._current_session and tag not in self._current_session.tags:
            self._current_session.tags.append(tag)

    def get_statistics(self) -> dict:
        """Get current logging statistics."""
        if not self._current_session:
            return {
                "is_logging": False,
                "sample_count": 0,
            }

        return {
            "is_logging": True,
            "session_id": self._current_session.session_id,
            "sample_count": self._current_session.sample_count,
            "start_time": self._current_session.start_time.isoformat(),
            "format": self._format,
            "file": str(self._current_file) if self._current_file else None,
        }
