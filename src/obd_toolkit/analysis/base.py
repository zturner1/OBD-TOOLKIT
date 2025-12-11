"""Base analyzer class for diagnostic analysis."""

from abc import ABC, abstractmethod
from typing import List

from ..models.session import DiagnosticSession, AnalysisResult, AnalysisFinding


class BaseAnalyzer(ABC):
    """Abstract base class for all analyzers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Analyzer name for display."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Analyzer description."""
        pass

    @abstractmethod
    def get_required_pids(self) -> List[str]:
        """
        Get PIDs required for this analysis.

        Returns:
            List of required PID names
        """
        pass

    @abstractmethod
    def analyze(self, session: DiagnosticSession) -> AnalysisResult:
        """
        Perform analysis on diagnostic data.

        Args:
            session: Diagnostic session with collected data

        Returns:
            AnalysisResult with findings
        """
        pass

    def create_finding(
        self,
        title: str,
        description: str,
        severity: str = "info",
        category: str = "general",
        confidence: float = 1.0,
        recommendations: List[str] = None,
        related_pids: List[str] = None,
        related_dtcs: List[str] = None,
    ) -> AnalysisFinding:
        """
        Helper to create an AnalysisFinding.

        Args:
            title: Finding title
            description: Finding description
            severity: Severity level (critical, warning, info)
            category: Finding category
            confidence: Confidence level (0-1)
            recommendations: List of recommendations
            related_pids: Related PID names
            related_dtcs: Related DTC codes

        Returns:
            AnalysisFinding instance
        """
        return AnalysisFinding(
            title=title,
            description=description,
            severity=severity,
            category=category,
            confidence=confidence,
            recommendations=recommendations or [],
            related_pids=related_pids or [],
            related_dtcs=related_dtcs or [],
        )

    def create_result(
        self,
        findings: List[AnalysisFinding] = None,
        summary: str = "",
        metrics: dict = None,
    ) -> AnalysisResult:
        """
        Helper to create an AnalysisResult.

        Args:
            findings: List of findings
            summary: Analysis summary
            metrics: Computed metrics

        Returns:
            AnalysisResult instance
        """
        return AnalysisResult(
            analyzer_name=self.name,
            findings=findings or [],
            summary=summary,
            metrics=metrics or {},
        )

    def has_required_data(self, session: DiagnosticSession) -> bool:
        """
        Check if session has required data for analysis.

        Args:
            session: Session to check

        Returns:
            True if has required data
        """
        if not session.pid_samples:
            return False

        required_pids = set(self.get_required_pids())

        # Check if any sample has the required PIDs
        for sample in session.pid_samples:
            available_pids = set(sample.values.keys())
            if required_pids & available_pids:  # Any overlap
                return True

        return False
