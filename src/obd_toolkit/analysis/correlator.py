"""Statistical correlator for analyzing sensor relationships."""

from typing import List, Dict, Tuple, Optional
import statistics
import math

from .base import BaseAnalyzer
from ..models.session import DiagnosticSession, AnalysisResult, AnalysisFinding


class Correlator(BaseAnalyzer):
    """Analyzes correlations between sensor readings to identify anomalies."""

    @property
    def name(self) -> str:
        return "Statistical Correlation Analysis"

    @property
    def description(self) -> str:
        return "Identifies unusual patterns and correlations in sensor data"

    def get_required_pids(self) -> List[str]:
        return ["RPM", "SPEED", "ENGINE_LOAD", "THROTTLE_POS", "MAF", "COOLANT_TEMP"]

    def analyze(self, session: DiagnosticSession) -> AnalysisResult:
        """Perform correlation analysis."""
        findings = []
        metrics = {}

        if not session.pid_samples or len(session.pid_samples) < 10:
            return self.create_result(
                findings=[self.create_finding(
                    "Insufficient Data",
                    "Need at least 10 samples for correlation analysis",
                    severity="info"
                )],
                summary="Insufficient data for correlation analysis"
            )

        # Extract time series for each PID
        series = self._extract_series(session)

        if len(series) < 2:
            return self.create_result(
                findings=[self.create_finding(
                    "Insufficient PIDs",
                    "Need at least 2 different PIDs for correlation analysis",
                    severity="info"
                )],
                summary="Insufficient PID data for correlation"
            )

        # Calculate correlations between key pairs
        correlations = self._calculate_correlations(series)
        metrics["correlations"] = correlations

        # Analyze expected vs actual correlations
        findings.extend(self._analyze_expected_correlations(correlations, series))

        # Detect anomalies
        findings.extend(self._detect_anomalies(series))

        # Trend analysis
        findings.extend(self._analyze_trends(series))

        # Generate summary
        anomaly_count = sum(1 for f in findings if f.severity in ("critical", "warning"))
        if anomaly_count > 0:
            summary = f"Found {anomaly_count} anomaly(s) in sensor data correlations."
        else:
            summary = "Sensor data correlations appear normal."

        return self.create_result(findings=findings, summary=summary, metrics=metrics)

    def _extract_series(self, session: DiagnosticSession) -> Dict[str, List[float]]:
        """Extract time series data for each PID."""
        series = {}

        for sample in session.pid_samples:
            for pid, value in sample.values.items():
                if pid not in series:
                    series[pid] = []
                series[pid].append(float(value))

        # Only keep series with enough data points
        return {k: v for k, v in series.items() if len(v) >= 10}

    def _calculate_correlations(
        self,
        series: Dict[str, List[float]]
    ) -> Dict[Tuple[str, str], float]:
        """Calculate Pearson correlations between PID pairs."""
        correlations = {}
        pids = list(series.keys())

        for i in range(len(pids)):
            for j in range(i + 1, len(pids)):
                pid1, pid2 = pids[i], pids[j]
                values1 = series[pid1]
                values2 = series[pid2]

                # Align lengths
                min_len = min(len(values1), len(values2))
                if min_len < 10:
                    continue

                corr = self._pearson_correlation(values1[:min_len], values2[:min_len])
                if corr is not None:
                    correlations[(pid1, pid2)] = corr

        return correlations

    def _pearson_correlation(self, x: List[float], y: List[float]) -> Optional[float]:
        """Calculate Pearson correlation coefficient."""
        n = len(x)
        if n != len(y) or n < 2:
            return None

        mean_x = statistics.mean(x)
        mean_y = statistics.mean(y)

        numerator = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
        denom_x = math.sqrt(sum((xi - mean_x) ** 2 for xi in x))
        denom_y = math.sqrt(sum((yi - mean_y) ** 2 for yi in y))

        if denom_x == 0 or denom_y == 0:
            return None

        return numerator / (denom_x * denom_y)

    def _analyze_expected_correlations(
        self,
        correlations: Dict[Tuple[str, str], float],
        series: Dict[str, List[float]]
    ) -> List[AnalysisFinding]:
        """Check if expected correlations exist."""
        findings = []

        # Expected positive correlations
        expected_positive = [
            ("RPM", "MAF", 0.5, "RPM and MAF should correlate (more RPM = more air)"),
            ("THROTTLE_POS", "ENGINE_LOAD", 0.4, "Throttle and load should correlate"),
            ("SPEED", "RPM", 0.3, "Speed and RPM should correlate (in gear)"),
        ]

        for pid1, pid2, min_corr, explanation in expected_positive:
            key = (pid1, pid2) if (pid1, pid2) in correlations else (pid2, pid1)
            if key in correlations:
                actual_corr = correlations[key]
                if actual_corr < min_corr:
                    findings.append(self.create_finding(
                        f"Unexpected Low Correlation: {pid1}-{pid2}",
                        f"Expected positive correlation between {pid1} and {pid2}, "
                        f"but found {actual_corr:.2f}. {explanation}",
                        severity="warning" if actual_corr < 0 else "info",
                        category="correlation",
                        confidence=0.6,
                        related_pids=[pid1, pid2],
                    ))

        # RPM vs SPEED negative correlation check (engine braking)
        key = ("RPM", "SPEED") if ("RPM", "SPEED") in correlations else ("SPEED", "RPM")
        if key in correlations and correlations[key] < -0.3:
            findings.append(self.create_finding(
                "Negative RPM-Speed Correlation",
                "RPM and Speed are negatively correlated, which is unusual. "
                "May indicate transmission issues or data collection during unusual conditions.",
                severity="info",
                category="correlation",
                confidence=0.5,
                related_pids=["RPM", "SPEED"],
            ))

        return findings

    def _detect_anomalies(self, series: Dict[str, List[float]]) -> List[AnalysisFinding]:
        """Detect statistical anomalies in data."""
        findings = []

        for pid, values in series.items():
            if len(values) < 20:
                continue

            mean = statistics.mean(values)
            std = statistics.stdev(values)

            if std == 0:
                continue

            # Find outliers (>3 standard deviations)
            outliers = [v for v in values if abs(v - mean) > 3 * std]

            if len(outliers) > len(values) * 0.05:  # More than 5% outliers
                findings.append(self.create_finding(
                    f"Data Anomalies in {pid}",
                    f"Found {len(outliers)} outlier readings ({len(outliers)/len(values)*100:.1f}%) "
                    f"in {pid} data. This may indicate sensor issues or unusual conditions.",
                    severity="info",
                    category="anomaly",
                    confidence=0.5,
                    related_pids=[pid],
                ))

            # Check for sudden spikes
            spikes = []
            for i in range(1, len(values)):
                if abs(values[i] - values[i-1]) > 3 * std:
                    spikes.append(i)

            if len(spikes) > 5:
                findings.append(self.create_finding(
                    f"Sudden Changes in {pid}",
                    f"Detected {len(spikes)} sudden value changes in {pid}. "
                    "This may indicate intermittent sensor issues.",
                    severity="warning",
                    category="anomaly",
                    confidence=0.6,
                    related_pids=[pid],
                ))

        return findings

    def _analyze_trends(self, series: Dict[str, List[float]]) -> List[AnalysisFinding]:
        """Analyze data for concerning trends."""
        findings = []

        for pid, values in series.items():
            if len(values) < 20:
                continue

            # Check for consistent upward/downward trend
            # Using simple linear regression slope
            n = len(values)
            x_mean = (n - 1) / 2
            y_mean = statistics.mean(values)

            numerator = sum((i - x_mean) * (values[i] - y_mean) for i in range(n))
            denominator = sum((i - x_mean) ** 2 for i in range(n))

            if denominator == 0:
                continue

            slope = numerator / denominator

            # Normalize slope by mean value
            if y_mean != 0:
                relative_slope = slope / y_mean * 100

                # Significant trend if >1% change per sample on average
                if abs(relative_slope) > 1:
                    direction = "increasing" if slope > 0 else "decreasing"
                    findings.append(self.create_finding(
                        f"Trending {pid}",
                        f"{pid} shows a consistent {direction} trend "
                        f"({relative_slope:.2f}% per sample). "
                        "This may indicate a developing issue.",
                        severity="info" if abs(relative_slope) < 2 else "warning",
                        category="trend",
                        confidence=0.5,
                        related_pids=[pid],
                    ))

        return findings

    def calculate_baseline(
        self,
        series: Dict[str, List[float]]
    ) -> Dict[str, Dict[str, float]]:
        """
        Calculate baseline statistics for each PID.

        Returns:
            Dictionary of PID -> {mean, std, min, max, median}
        """
        baselines = {}

        for pid, values in series.items():
            if len(values) < 5:
                continue

            baselines[pid] = {
                "mean": statistics.mean(values),
                "std": statistics.stdev(values) if len(values) > 1 else 0,
                "min": min(values),
                "max": max(values),
                "median": statistics.median(values),
            }

        return baselines

    def compare_to_baseline(
        self,
        current: Dict[str, float],
        baseline: Dict[str, Dict[str, float]]
    ) -> List[AnalysisFinding]:
        """
        Compare current values to baseline.

        Args:
            current: Current PID values
            baseline: Baseline statistics

        Returns:
            List of findings for deviations
        """
        findings = []

        for pid, value in current.items():
            if pid not in baseline:
                continue

            bl = baseline[pid]
            if bl["std"] == 0:
                continue

            # Calculate z-score
            z_score = (value - bl["mean"]) / bl["std"]

            if abs(z_score) > 3:
                findings.append(self.create_finding(
                    f"{pid} Outside Normal Range",
                    f"Current {pid} value ({value:.1f}) is {abs(z_score):.1f} "
                    f"standard deviations from baseline ({bl['mean']:.1f}).",
                    severity="warning" if abs(z_score) > 4 else "info",
                    category="baseline",
                    confidence=0.7,
                    related_pids=[pid],
                ))

        return findings
