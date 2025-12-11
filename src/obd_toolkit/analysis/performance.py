"""Performance analyzer for engine and vehicle performance."""

from typing import List
import statistics

from .base import BaseAnalyzer
from ..models.session import DiagnosticSession, AnalysisResult, AnalysisFinding


class PerformanceAnalyzer(BaseAnalyzer):
    """Analyzes vehicle performance data."""

    @property
    def name(self) -> str:
        return "Performance Analysis"

    @property
    def description(self) -> str:
        return "Analyzes engine performance, detects misfires and sensor issues"

    def get_required_pids(self) -> List[str]:
        return ["RPM", "ENGINE_LOAD", "THROTTLE_POS", "COOLANT_TEMP"]

    def analyze(self, session: DiagnosticSession) -> AnalysisResult:
        """Analyze performance data."""
        findings = []
        metrics = {}

        if not session.pid_samples:
            return self.create_result(
                findings=[self.create_finding(
                    "No Data",
                    "No PID samples available for analysis",
                    severity="info"
                )],
                summary="Insufficient data for performance analysis"
            )

        # Extract time series data
        rpm_values = []
        load_values = []
        throttle_values = []
        coolant_values = []

        for sample in session.pid_samples:
            if "RPM" in sample.values:
                rpm_values.append(sample.values["RPM"])
            if "ENGINE_LOAD" in sample.values:
                load_values.append(sample.values["ENGINE_LOAD"])
            if "THROTTLE_POS" in sample.values:
                throttle_values.append(sample.values["THROTTLE_POS"])
            if "COOLANT_TEMP" in sample.values:
                coolant_values.append(sample.values["COOLANT_TEMP"])

        # Analyze RPM stability (misfire detection)
        if rpm_values:
            findings.extend(self._analyze_rpm_stability(rpm_values))
            metrics["rpm_avg"] = statistics.mean(rpm_values)
            metrics["rpm_max"] = max(rpm_values)
            metrics["rpm_std"] = statistics.stdev(rpm_values) if len(rpm_values) > 1 else 0

        # Analyze engine load patterns
        if load_values:
            findings.extend(self._analyze_load_patterns(load_values))
            metrics["load_avg"] = statistics.mean(load_values)
            metrics["load_max"] = max(load_values)

        # Analyze throttle response
        if throttle_values and rpm_values:
            findings.extend(self._analyze_throttle_response(throttle_values, rpm_values))

        # Analyze coolant temperature
        if coolant_values:
            findings.extend(self._analyze_coolant_temp(coolant_values))
            metrics["coolant_avg"] = statistics.mean(coolant_values)
            metrics["coolant_max"] = max(coolant_values)

        # Check DTCs for performance-related codes
        if session.dtc_result:
            findings.extend(self._analyze_performance_dtcs(session.dtc_result))

        # Generate summary
        issue_count = sum(1 for f in findings if f.severity in ("critical", "warning"))
        if issue_count == 0:
            summary = "No performance issues detected. Engine appears to be running normally."
        elif issue_count == 1:
            summary = "1 potential performance issue detected. See findings for details."
        else:
            summary = f"{issue_count} potential performance issues detected. Review findings carefully."

        return self.create_result(findings=findings, summary=summary, metrics=metrics)

    def _analyze_rpm_stability(self, rpm_values: List[float]) -> List[AnalysisFinding]:
        """Analyze RPM for stability issues (potential misfires)."""
        findings = []

        if len(rpm_values) < 5:
            return findings

        # Calculate RPM variance
        mean_rpm = statistics.mean(rpm_values)
        std_rpm = statistics.stdev(rpm_values)

        # Calculate RPM changes between samples
        rpm_changes = [abs(rpm_values[i] - rpm_values[i-1]) for i in range(1, len(rpm_values))]
        max_change = max(rpm_changes) if rpm_changes else 0

        # Check for high variance at idle
        idle_samples = [r for r in rpm_values if r < 1200]
        if idle_samples and len(idle_samples) > 3:
            idle_std = statistics.stdev(idle_samples)

            if idle_std > 100:
                findings.append(self.create_finding(
                    "Rough Idle Detected",
                    f"RPM variance at idle is high ({idle_std:.0f} RPM std). "
                    "This may indicate misfires, vacuum leaks, or fuel system issues.",
                    severity="warning",
                    category="engine",
                    confidence=0.8,
                    recommendations=[
                        "Check for vacuum leaks",
                        "Inspect spark plugs and ignition coils",
                        "Check fuel injectors",
                        "Clean throttle body",
                    ],
                    related_pids=["RPM"],
                ))

        # Check for sudden RPM drops (potential misfire)
        large_drops = [c for c in rpm_changes if c > 300]
        if len(large_drops) > 2:
            findings.append(self.create_finding(
                "RPM Fluctuations Detected",
                f"Detected {len(large_drops)} significant RPM drops (>300 RPM). "
                "This pattern may indicate cylinder misfires.",
                severity="warning",
                category="engine",
                confidence=0.7,
                recommendations=[
                    "Check for misfire codes (P030x)",
                    "Inspect ignition system",
                    "Check compression",
                ],
                related_pids=["RPM"],
                related_dtcs=["P0300", "P0301", "P0302", "P0303", "P0304"],
            ))

        return findings

    def _analyze_load_patterns(self, load_values: List[float]) -> List[AnalysisFinding]:
        """Analyze engine load patterns."""
        findings = []

        if len(load_values) < 5:
            return findings

        avg_load = statistics.mean(load_values)
        max_load = max(load_values)

        # Check for consistently high load at idle
        if avg_load > 40 and max(load_values) == min(load_values):
            findings.append(self.create_finding(
                "High Idle Load",
                f"Engine load is consistently high ({avg_load:.0f}%) even at idle. "
                "This may indicate accessory loads or engine efficiency issues.",
                severity="info",
                category="engine",
                confidence=0.6,
                recommendations=[
                    "Check AC compressor operation",
                    "Check alternator output",
                    "Inspect for dragging brakes",
                ],
                related_pids=["ENGINE_LOAD"],
            ))

        # Check for load spikes
        load_changes = [abs(load_values[i] - load_values[i-1]) for i in range(1, len(load_values))]
        sudden_spikes = [c for c in load_changes if c > 30]

        if len(sudden_spikes) > 3:
            findings.append(self.create_finding(
                "Load Fluctuations",
                f"Detected {len(sudden_spikes)} sudden load changes (>30%). "
                "This could indicate transmission issues or engine hesitation.",
                severity="info",
                category="engine",
                confidence=0.5,
                related_pids=["ENGINE_LOAD"],
            ))

        return findings

    def _analyze_throttle_response(
        self,
        throttle_values: List[float],
        rpm_values: List[float]
    ) -> List[AnalysisFinding]:
        """Analyze throttle response correlation with RPM."""
        findings = []

        if len(throttle_values) < 10 or len(rpm_values) < 10:
            return findings

        # Check throttle-RPM correlation
        # When throttle increases, RPM should increase (with some delay)

        # Find throttle increases
        throttle_increases = []
        for i in range(1, len(throttle_values)):
            if throttle_values[i] - throttle_values[i-1] > 10:
                throttle_increases.append(i)

        # Check if RPM follows throttle
        slow_responses = 0
        for idx in throttle_increases:
            if idx + 3 < len(rpm_values):
                rpm_increase = rpm_values[idx + 2] - rpm_values[idx]
                if rpm_increase < 100:  # RPM didn't respond
                    slow_responses += 1

        if slow_responses > 2:
            findings.append(self.create_finding(
                "Throttle Response Lag",
                "Engine shows delayed response to throttle input. "
                "This may indicate fuel delivery issues or throttle body problems.",
                severity="warning",
                category="engine",
                confidence=0.6,
                recommendations=[
                    "Clean throttle body",
                    "Check fuel pressure",
                    "Inspect throttle position sensor",
                    "Check MAF sensor",
                ],
                related_pids=["THROTTLE_POS", "RPM"],
            ))

        return findings

    def _analyze_coolant_temp(self, coolant_values: List[float]) -> List[AnalysisFinding]:
        """Analyze coolant temperature patterns."""
        findings = []

        if not coolant_values:
            return findings

        max_temp = max(coolant_values)
        min_temp = min(coolant_values)
        avg_temp = statistics.mean(coolant_values)

        # Check for overheating
        if max_temp > 110:
            findings.append(self.create_finding(
                "Elevated Coolant Temperature",
                f"Coolant reached {max_temp:.0f}C, which is above normal operating range. "
                "Risk of engine damage if this continues.",
                severity="critical",
                category="cooling",
                confidence=0.9,
                recommendations=[
                    "Check coolant level",
                    "Inspect radiator for blockage",
                    "Check thermostat operation",
                    "Inspect water pump",
                    "Check cooling fans",
                ],
                related_pids=["COOLANT_TEMP"],
            ))
        elif max_temp > 100:
            findings.append(self.create_finding(
                "Warm Coolant Temperature",
                f"Coolant reached {max_temp:.0f}C. Monitor closely.",
                severity="warning",
                category="cooling",
                confidence=0.7,
                related_pids=["COOLANT_TEMP"],
            ))

        # Check for thermostat issues
        if max_temp < 75 and len(coolant_values) > 20:
            findings.append(self.create_finding(
                "Engine Not Reaching Temperature",
                f"Coolant temperature ({avg_temp:.0f}C avg) not reaching normal operating range. "
                "Thermostat may be stuck open.",
                severity="warning",
                category="cooling",
                confidence=0.7,
                recommendations=[
                    "Check thermostat operation",
                    "Verify coolant temp sensor accuracy",
                ],
                related_pids=["COOLANT_TEMP"],
            ))

        return findings

    def _analyze_performance_dtcs(self, dtc_result) -> List[AnalysisFinding]:
        """Analyze DTCs for performance-related codes."""
        findings = []

        all_codes = dtc_result.all_codes if hasattr(dtc_result, 'all_codes') else []

        misfire_codes = [c for c in all_codes if c.code.startswith("P030")]
        if misfire_codes:
            codes_str = ", ".join(c.code for c in misfire_codes)
            findings.append(self.create_finding(
                "Misfire Codes Present",
                f"Active misfire codes detected: {codes_str}",
                severity="critical",
                category="engine",
                confidence=1.0,
                recommendations=[
                    "Address misfire codes before other analysis",
                    "Check ignition system",
                    "Inspect fuel injectors",
                ],
                related_dtcs=[c.code for c in misfire_codes],
            ))

        return findings
