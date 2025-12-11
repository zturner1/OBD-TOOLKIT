"""Data models for diagnostic sessions."""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import uuid4

from .dtc import DTCReadResult
from .pid import PIDValue, PIDSnapshot
from .vehicle import VehicleInfo


class PIDSample(BaseModel):
    """A timestamped sample of PID data."""

    timestamp: datetime = Field(default_factory=datetime.now)
    values: Dict[str, float] = Field(default_factory=dict, description="PID name to numeric value")
    raw_values: Dict[str, PIDValue] = Field(default_factory=dict, description="Full PID values")

    @classmethod
    def from_snapshot(cls, snapshot: PIDSnapshot) -> "PIDSample":
        """Create sample from a PID snapshot."""
        values = {}
        raw_values = {}

        for pid_name, pid_value in snapshot.values.items():
            raw_values[pid_name] = pid_value
            if pid_value.numeric_value is not None:
                values[pid_name] = pid_value.numeric_value

        return cls(timestamp=snapshot.timestamp, values=values, raw_values=raw_values)


class AnalysisFinding(BaseModel):
    """A single finding from analysis."""

    title: str = Field(..., description="Short title of the finding")
    description: str = Field(..., description="Detailed description")
    severity: str = Field(default="info", description="Severity level: critical, warning, info")
    category: str = Field(default="general", description="Category of finding")

    related_pids: List[str] = Field(default_factory=list, description="PIDs related to this finding")
    related_dtcs: List[str] = Field(default_factory=list, description="DTCs related to this finding")

    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence in this finding")
    recommendations: List[str] = Field(default_factory=list, description="Recommended actions")

    data: Dict[str, Any] = Field(default_factory=dict, description="Supporting data")


class AnalysisResult(BaseModel):
    """Result from running an analyzer."""

    analyzer_name: str = Field(..., description="Name of the analyzer")
    timestamp: datetime = Field(default_factory=datetime.now)

    findings: List[AnalysisFinding] = Field(default_factory=list)
    summary: str = Field(default="", description="Summary of analysis")

    metrics: Dict[str, float] = Field(default_factory=dict, description="Computed metrics")

    @property
    def has_issues(self) -> bool:
        """Check if any issues were found."""
        return any(f.severity in ("critical", "warning") for f in self.findings)

    @property
    def critical_count(self) -> int:
        """Count critical findings."""
        return sum(1 for f in self.findings if f.severity == "critical")

    @property
    def warning_count(self) -> int:
        """Count warning findings."""
        return sum(1 for f in self.findings if f.severity == "warning")


class DiagnosticSession(BaseModel):
    """A complete diagnostic session with all collected data."""

    session_id: str = Field(default_factory=lambda: str(uuid4())[:8])

    start_time: datetime = Field(default_factory=datetime.now)
    end_time: Optional[datetime] = Field(default=None)

    # Vehicle information
    vehicle_info: Optional[VehicleInfo] = Field(default=None)

    # Connection info
    adapter_info: Dict[str, str] = Field(default_factory=dict)
    protocol: str = Field(default="Unknown")

    # Collected data
    dtc_result: Optional[DTCReadResult] = Field(default=None)
    pid_samples: List[PIDSample] = Field(default_factory=list)

    # Analysis results
    analysis_results: List[AnalysisResult] = Field(default_factory=list)

    # Metadata
    notes: str = Field(default="")
    tags: List[str] = Field(default_factory=list)

    @property
    def duration_seconds(self) -> Optional[float]:
        """Get session duration in seconds."""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None

    @property
    def sample_count(self) -> int:
        """Get number of PID samples collected."""
        return len(self.pid_samples)

    @property
    def is_active(self) -> bool:
        """Check if session is still active."""
        return self.end_time is None

    def add_sample(self, sample: PIDSample) -> None:
        """Add a PID sample to the session."""
        self.pid_samples.append(sample)

    def add_analysis(self, result: AnalysisResult) -> None:
        """Add an analysis result."""
        self.analysis_results.append(result)

    def end_session(self) -> None:
        """Mark the session as ended."""
        self.end_time = datetime.now()

    def get_pid_series(self, pid_name: str) -> List[tuple[datetime, float]]:
        """Get time series data for a specific PID."""
        series = []
        for sample in self.pid_samples:
            if pid_name in sample.values:
                series.append((sample.timestamp, sample.values[pid_name]))
        return series

    def get_latest_values(self) -> Dict[str, float]:
        """Get the most recent values for all PIDs."""
        if not self.pid_samples:
            return {}
        return self.pid_samples[-1].values

    def to_dict_for_export(self) -> Dict[str, Any]:
        """Convert to dictionary suitable for JSON export."""
        return {
            "session_id": self.session_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "vehicle": self.vehicle_info.model_dump() if self.vehicle_info else None,
            "adapter": self.adapter_info,
            "protocol": self.protocol,
            "dtcs": self.dtc_result.model_dump() if self.dtc_result else None,
            "sample_count": self.sample_count,
            "samples": [
                {
                    "timestamp": s.timestamp.isoformat(),
                    "values": s.values
                }
                for s in self.pid_samples
            ],
            "analysis": [r.model_dump() for r in self.analysis_results],
            "notes": self.notes,
            "tags": self.tags,
        }
