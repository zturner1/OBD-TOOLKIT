"""Historical session management."""

import json
import csv
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

from ..models.session import DiagnosticSession, PIDSample
from ..models.dtc import DTCReadResult
from ..models.vehicle import VehicleInfo

logger = logging.getLogger(__name__)


class HistoryManager:
    """Manages historical diagnostic session data."""

    DEFAULT_DATA_DIR = Path.home() / ".obd-toolkit" / "logs"

    def __init__(self, data_dir: Optional[Path] = None):
        """
        Initialize history manager.

        Args:
            data_dir: Directory containing log files
        """
        self._data_dir = data_dir or self.DEFAULT_DATA_DIR
        self._data_dir.mkdir(parents=True, exist_ok=True)

    @property
    def data_dir(self) -> Path:
        """Get data directory path."""
        return self._data_dir

    def list_sessions(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        List available sessions.

        Args:
            limit: Maximum number of sessions to return

        Returns:
            List of session metadata dictionaries
        """
        sessions = []

        # Find all session files
        json_files = list(self._data_dir.glob("session_*.json"))
        csv_files = list(self._data_dir.glob("session_*.csv"))

        all_files = json_files + csv_files
        all_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

        for filepath in all_files[:limit]:
            try:
                metadata = self._get_session_metadata(filepath)
                if metadata:
                    sessions.append(metadata)
            except Exception as e:
                logger.warning(f"Could not read session {filepath}: {e}")

        return sessions

    def _get_session_metadata(self, filepath: Path) -> Optional[Dict[str, Any]]:
        """Extract metadata from session file."""
        filename = filepath.name

        # Parse session ID from filename
        parts = filename.replace(".json", "").replace(".csv", "").split("_")
        session_id = parts[1] if len(parts) > 1 else "unknown"

        if filepath.suffix == ".json":
            return self._get_json_metadata(filepath, session_id)
        else:
            return self._get_csv_metadata(filepath, session_id)

    def _get_json_metadata(self, filepath: Path, session_id: str) -> Dict[str, Any]:
        """Get metadata from JSON session file."""
        with open(filepath, 'r') as f:
            data = json.load(f)

        vehicle = data.get("vehicle", {})
        vehicle_str = "Unknown"
        if vehicle:
            parts = []
            if vehicle.get("manufacturer"):
                parts.append(vehicle["manufacturer"])
            if vehicle.get("model_year"):
                parts.append(str(vehicle["model_year"]))
            if parts:
                vehicle_str = " ".join(parts)

        duration = None
        if data.get("start_time") and data.get("end_time"):
            try:
                start = datetime.fromisoformat(data["start_time"])
                end = datetime.fromisoformat(data["end_time"])
                duration_secs = (end - start).total_seconds()
                duration = f"{int(duration_secs // 60)}m {int(duration_secs % 60)}s"
            except:
                pass

        dtc_count = 0
        if data.get("dtcs"):
            dtcs = data["dtcs"]
            dtc_count = (
                len(dtcs.get("stored_codes", [])) +
                len(dtcs.get("pending_codes", [])) +
                len(dtcs.get("permanent_codes", []))
            )

        return {
            "session_id": session_id,
            "start_time": data.get("start_time", "Unknown"),
            "vehicle": vehicle_str,
            "dtc_count": dtc_count,
            "sample_count": data.get("sample_count", 0),
            "duration": duration or "Unknown",
            "filepath": str(filepath),
            "format": "json",
        }

    def _get_csv_metadata(self, filepath: Path, session_id: str) -> Dict[str, Any]:
        """Get metadata from CSV session file."""
        # Count lines for sample count
        with open(filepath, 'r') as f:
            sample_count = sum(1 for _ in f) - 1  # Subtract header

        # Get file timestamps
        stat = filepath.stat()
        start_time = datetime.fromtimestamp(stat.st_mtime).isoformat()

        return {
            "session_id": session_id,
            "start_time": start_time,
            "vehicle": "Unknown",
            "dtc_count": 0,
            "sample_count": sample_count,
            "duration": "Unknown",
            "filepath": str(filepath),
            "format": "csv",
        }

    def load_session(self, session_id: str) -> Optional[DiagnosticSession]:
        """
        Load a session by ID.

        Args:
            session_id: Session ID to load

        Returns:
            DiagnosticSession or None
        """
        # Find session file
        json_match = list(self._data_dir.glob(f"session_{session_id}*.json"))
        csv_match = list(self._data_dir.glob(f"session_{session_id}*.csv"))

        if json_match:
            return self._load_json_session(json_match[0])
        elif csv_match:
            return self._load_csv_session(csv_match[0])

        return None

    def load_session_from_file(self, filepath: str) -> Optional[DiagnosticSession]:
        """
        Load session from specific file path.

        Args:
            filepath: Path to session file

        Returns:
            DiagnosticSession or None
        """
        path = Path(filepath)

        if not path.exists():
            logger.error(f"File not found: {filepath}")
            return None

        if path.suffix == ".json":
            return self._load_json_session(path)
        elif path.suffix == ".csv":
            return self._load_csv_session(path)

        logger.error(f"Unsupported file format: {path.suffix}")
        return None

    def _load_json_session(self, filepath: Path) -> Optional[DiagnosticSession]:
        """Load session from JSON file."""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            session = DiagnosticSession(
                session_id=data.get("session_id", "unknown"),
                start_time=datetime.fromisoformat(data["start_time"]) if data.get("start_time") else datetime.now(),
                end_time=datetime.fromisoformat(data["end_time"]) if data.get("end_time") else None,
                protocol=data.get("protocol", "Unknown"),
                notes=data.get("notes", ""),
                tags=data.get("tags", []),
            )

            # Load vehicle info
            if data.get("vehicle"):
                session.vehicle_info = VehicleInfo(**data["vehicle"])

            # Load samples
            for sample_data in data.get("samples", []):
                sample = PIDSample(
                    timestamp=datetime.fromisoformat(sample_data["timestamp"]),
                    values=sample_data["values"],
                )
                session.pid_samples.append(sample)

            return session

        except Exception as e:
            logger.error(f"Error loading JSON session: {e}")
            return None

    def _load_csv_session(self, filepath: Path) -> Optional[DiagnosticSession]:
        """Load session from CSV file."""
        try:
            session = DiagnosticSession()

            with open(filepath, 'r') as f:
                reader = csv.DictReader(f)

                for row in reader:
                    timestamp_str = row.pop("timestamp", None)
                    try:
                        timestamp = datetime.fromisoformat(timestamp_str) if timestamp_str else datetime.now()
                    except:
                        timestamp = datetime.now()

                    values = {}
                    for key, val in row.items():
                        try:
                            values[key] = float(val) if val else 0.0
                        except:
                            values[key] = 0.0

                    session.pid_samples.append(PIDSample(
                        timestamp=timestamp,
                        values=values,
                    ))

            return session

        except Exception as e:
            logger.error(f"Error loading CSV session: {e}")
            return None

    def export_session(
        self,
        session_id: str,
        format: str = "csv",
        output_path: Optional[str] = None
    ) -> Optional[str]:
        """
        Export a session to a specific format.

        Args:
            session_id: Session ID to export
            format: Export format ('csv' or 'json')
            output_path: Output file path (auto-generated if None)

        Returns:
            Path to exported file or None
        """
        session = self.load_session(session_id)
        if not session:
            return None

        if output_path:
            filepath = Path(output_path)
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"export_{session_id}_{timestamp}.{format}"
            filepath = self._data_dir / filename

        if format == "csv":
            return self._export_csv(session, filepath)
        else:
            return self._export_json(session, filepath)

    def _export_csv(self, session: DiagnosticSession, filepath: Path) -> Optional[str]:
        """Export session to CSV."""
        try:
            if not session.pid_samples:
                return None

            # Get all PIDs
            all_pids = set()
            for sample in session.pid_samples:
                all_pids.update(sample.values.keys())

            pids = sorted(all_pids)

            with open(filepath, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["timestamp"] + pids)

                for sample in session.pid_samples:
                    row = [sample.timestamp.isoformat()]
                    for pid in pids:
                        row.append(sample.values.get(pid, ""))
                    writer.writerow(row)

            return str(filepath)

        except Exception as e:
            logger.error(f"CSV export error: {e}")
            return None

    def _export_json(self, session: DiagnosticSession, filepath: Path) -> Optional[str]:
        """Export session to JSON."""
        try:
            data = session.to_dict_for_export()

            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2, default=str)

            return str(filepath)

        except Exception as e:
            logger.error(f"JSON export error: {e}")
            return None

    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session.

        Args:
            session_id: Session ID to delete

        Returns:
            True if deleted, False otherwise
        """
        matches = list(self._data_dir.glob(f"session_{session_id}*"))

        if not matches:
            return False

        for filepath in matches:
            try:
                filepath.unlink()
                logger.info(f"Deleted session file: {filepath}")
            except Exception as e:
                logger.error(f"Could not delete {filepath}: {e}")
                return False

        return True

    def get_total_sessions(self) -> int:
        """Get total number of stored sessions."""
        json_count = len(list(self._data_dir.glob("session_*.json")))
        csv_count = len(list(self._data_dir.glob("session_*.csv")))
        return json_count + csv_count

    def get_storage_size(self) -> int:
        """Get total storage size in bytes."""
        total = 0
        for f in self._data_dir.glob("session_*"):
            total += f.stat().st_size
        return total
