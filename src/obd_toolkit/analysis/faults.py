"""Fault detector for predicting and correlating vehicle issues."""

from typing import List, Dict
import statistics

from .base import BaseAnalyzer
from ..models.session import DiagnosticSession, AnalysisResult, AnalysisFinding
from ..models.dtc import DTCSeverity


class FaultDetector(BaseAnalyzer):
    """Detects and predicts potential vehicle faults."""

    @property
    def name(self) -> str:
        return "Fault Detection"

    @property
    def description(self) -> str:
        return "Correlates sensor data and DTCs to detect and predict faults"

    def get_required_pids(self) -> List[str]:
        return ["COOLANT_TEMP", "RPM", "ENGINE_LOAD", "O2_B1S1", "SHORT_FUEL_TRIM_1", "LONG_FUEL_TRIM_1"]

    def analyze(self, session: DiagnosticSession) -> AnalysisResult:
        """Analyze data for potential faults."""
        findings = []
        metrics = {}

        # Analyze DTCs if present
        if session.dtc_result:
            findings.extend(self._analyze_dtcs(session.dtc_result))
            metrics["dtc_count"] = session.dtc_result.total_codes

        # Analyze sensor data for anomalies
        if session.pid_samples:
            findings.extend(self._analyze_sensor_anomalies(session))
            findings.extend(self._analyze_fuel_system(session))
            findings.extend(self._analyze_o2_sensors(session))
            findings.extend(self._correlate_symptoms(session))

        # Generate summary
        critical_count = sum(1 for f in findings if f.severity == "critical")
        warning_count = sum(1 for f in findings if f.severity == "warning")

        if critical_count > 0:
            summary = f"CRITICAL: {critical_count} critical issue(s) detected requiring immediate attention."
        elif warning_count > 0:
            summary = f"Found {warning_count} potential issue(s) that should be investigated."
        else:
            summary = "No significant faults detected. Vehicle appears to be operating normally."

        return self.create_result(findings=findings, summary=summary, metrics=metrics)

    def _analyze_dtcs(self, dtc_result) -> List[AnalysisFinding]:
        """Analyze DTCs for patterns and severity."""
        findings = []

        all_codes = dtc_result.all_codes

        if not all_codes:
            return findings

        # Check for critical codes
        critical_codes = [c for c in all_codes if c.severity == DTCSeverity.CRITICAL]
        if critical_codes:
            codes_str = ", ".join(c.code for c in critical_codes)
            findings.append(self.create_finding(
                "Critical DTCs Present",
                f"Critical diagnostic codes detected: {codes_str}. "
                "These require immediate attention to prevent damage.",
                severity="critical",
                category="dtc",
                confidence=1.0,
                recommendations=[
                    "Address critical codes before driving further",
                    "Consult a professional if unsure",
                ],
                related_dtcs=[c.code for c in critical_codes],
            ))

        # Check for related codes (same system)
        systems = {}
        for code in all_codes:
            system = code.system
            if system not in systems:
                systems[system] = []
            systems[system].append(code)

        for system, codes in systems.items():
            if len(codes) > 1:
                codes_str = ", ".join(c.code for c in codes)
                findings.append(self.create_finding(
                    f"Multiple {system} Codes",
                    f"Multiple codes in the same system: {codes_str}. "
                    "These may share a common cause.",
                    severity="warning",
                    category="dtc",
                    confidence=0.8,
                    recommendations=[
                        f"Focus diagnosis on {system} system",
                        "Check for common causes between codes",
                    ],
                    related_dtcs=[c.code for c in codes],
                ))

        # Check for pending codes that match stored codes
        stored_codes = set(c.code for c in dtc_result.stored_codes)
        pending_codes = set(c.code for c in dtc_result.pending_codes)
        recurring = stored_codes & pending_codes

        if recurring:
            findings.append(self.create_finding(
                "Recurring Faults",
                f"Codes {recurring} appear in both stored and pending. "
                "The underlying issue may not be fully resolved.",
                severity="warning",
                category="dtc",
                confidence=0.9,
                related_dtcs=list(recurring),
            ))

        return findings

    def _analyze_sensor_anomalies(self, session: DiagnosticSession) -> List[AnalysisFinding]:
        """Detect anomalies in sensor readings."""
        findings = []

        # Collect sensor values
        values = {}
        for sample in session.pid_samples:
            for pid, value in sample.values.items():
                if pid not in values:
                    values[pid] = []
                values[pid].append(value)

        # Check coolant temperature trends
        if "COOLANT_TEMP" in values:
            temps = values["COOLANT_TEMP"]
            if len(temps) > 10:
                # Check for temperature that only goes up (cooling issue)
                temp_changes = [temps[i] - temps[i-1] for i in range(1, len(temps))]
                if all(c >= 0 for c in temp_changes[-10:]) and temps[-1] > 100:
                    findings.append(self.create_finding(
                        "Temperature Rising Continuously",
                        "Coolant temperature is continuously rising without stabilizing. "
                        "Possible cooling system issue.",
                        severity="critical",
                        category="cooling",
                        confidence=0.8,
                        recommendations=[
                            "Stop and check coolant level",
                            "Check for cooling fan operation",
                            "Inspect for leaks",
                        ],
                        related_pids=["COOLANT_TEMP"],
                    ))

        # Check for stuck sensors (no variation)
        for pid, vals in values.items():
            if len(vals) > 20:
                unique_vals = len(set(round(v, 1) for v in vals))
                if unique_vals < 3:
                    findings.append(self.create_finding(
                        f"{pid} Sensor May Be Stuck",
                        f"{pid} sensor shows almost no variation ({unique_vals} unique values). "
                        "Sensor may be failing or disconnected.",
                        severity="warning",
                        category="sensor",
                        confidence=0.6,
                        recommendations=[
                            f"Check {pid} sensor wiring",
                            f"Test {pid} sensor response",
                        ],
                        related_pids=[pid],
                    ))

        return findings

    def _analyze_fuel_system(self, session: DiagnosticSession) -> List[AnalysisFinding]:
        """Analyze fuel system health."""
        findings = []

        short_trim = []
        long_trim = []

        for sample in session.pid_samples:
            if "SHORT_FUEL_TRIM_1" in sample.values:
                short_trim.append(sample.values["SHORT_FUEL_TRIM_1"])
            if "LONG_FUEL_TRIM_1" in sample.values:
                long_trim.append(sample.values["LONG_FUEL_TRIM_1"])

        if not short_trim and not long_trim:
            return findings

        # Analyze long term fuel trim
        if long_trim:
            avg_long = statistics.mean(long_trim)

            if avg_long > 15:
                findings.append(self.create_finding(
                    "System Running Lean",
                    f"Long term fuel trim is +{avg_long:.1f}%, indicating the engine "
                    "is compensating for a lean condition.",
                    severity="warning",
                    category="fuel",
                    confidence=0.8,
                    recommendations=[
                        "Check for vacuum leaks",
                        "Clean or replace MAF sensor",
                        "Check fuel pressure",
                        "Inspect intake gaskets",
                    ],
                    related_pids=["LONG_FUEL_TRIM_1", "SHORT_FUEL_TRIM_1"],
                    related_dtcs=["P0171", "P0174"],
                ))
            elif avg_long < -15:
                findings.append(self.create_finding(
                    "System Running Rich",
                    f"Long term fuel trim is {avg_long:.1f}%, indicating the engine "
                    "is compensating for a rich condition.",
                    severity="warning",
                    category="fuel",
                    confidence=0.8,
                    recommendations=[
                        "Check fuel injectors for leaks",
                        "Check fuel pressure regulator",
                        "Inspect O2 sensors",
                        "Check for coolant temp sensor issues",
                    ],
                    related_pids=["LONG_FUEL_TRIM_1", "SHORT_FUEL_TRIM_1"],
                    related_dtcs=["P0172", "P0175"],
                ))

        # Analyze short term fuel trim volatility
        if short_trim and len(short_trim) > 10:
            std_short = statistics.stdev(short_trim)
            if std_short > 10:
                findings.append(self.create_finding(
                    "Erratic Fuel Trim",
                    f"Short term fuel trim is highly variable (std: {std_short:.1f}%). "
                    "This suggests inconsistent air/fuel mixture.",
                    severity="info",
                    category="fuel",
                    confidence=0.6,
                    recommendations=[
                        "Check O2 sensor response",
                        "Look for intermittent vacuum leaks",
                        "Check for fuel delivery issues",
                    ],
                    related_pids=["SHORT_FUEL_TRIM_1"],
                ))

        return findings

    def _analyze_o2_sensors(self, session: DiagnosticSession) -> List[AnalysisFinding]:
        """Analyze O2 sensor behavior."""
        findings = []

        o2_values = []
        for sample in session.pid_samples:
            if "O2_B1S1" in sample.values:
                o2_values.append(sample.values["O2_B1S1"])

        if len(o2_values) < 20:
            return findings

        avg_o2 = statistics.mean(o2_values)
        std_o2 = statistics.stdev(o2_values)

        # Check for stuck O2 sensor
        if std_o2 < 0.05:
            findings.append(self.create_finding(
                "O2 Sensor Not Switching",
                f"O2 sensor voltage is not oscillating (std: {std_o2:.3f}V). "
                "Sensor may be stuck or engine may not be in closed loop.",
                severity="warning",
                category="sensor",
                confidence=0.7,
                recommendations=[
                    "Verify engine is at operating temperature",
                    "Check O2 sensor heater operation",
                    "Consider O2 sensor replacement",
                ],
                related_pids=["O2_B1S1"],
                related_dtcs=["P0133", "P0134"],
            ))

        # Check for constantly rich or lean
        if avg_o2 > 0.7:
            findings.append(self.create_finding(
                "O2 Sensor Indicates Rich",
                f"O2 sensor average is {avg_o2:.2f}V (rich). "
                "Engine may be running rich.",
                severity="info",
                category="fuel",
                related_pids=["O2_B1S1"],
            ))
        elif avg_o2 < 0.3:
            findings.append(self.create_finding(
                "O2 Sensor Indicates Lean",
                f"O2 sensor average is {avg_o2:.2f}V (lean). "
                "Engine may be running lean.",
                severity="info",
                category="fuel",
                related_pids=["O2_B1S1"],
            ))

        return findings

    def _correlate_symptoms(self, session: DiagnosticSession) -> List[AnalysisFinding]:
        """Correlate multiple symptoms to identify root causes."""
        findings = []

        # Collect symptom indicators
        symptoms = {
            "rough_idle": False,
            "lean_running": False,
            "rich_running": False,
            "overheating": False,
            "poor_throttle_response": False,
        }

        # Check for rough idle (RPM variance at idle)
        rpm_values = []
        for sample in session.pid_samples:
            if "RPM" in sample.values and sample.values["RPM"] < 1000:
                rpm_values.append(sample.values["RPM"])

        if rpm_values and len(rpm_values) > 5:
            if statistics.stdev(rpm_values) > 50:
                symptoms["rough_idle"] = True

        # Check for lean/rich from fuel trims
        long_trim = [s.values.get("LONG_FUEL_TRIM_1", 0) for s in session.pid_samples]
        if long_trim:
            avg_trim = statistics.mean(long_trim)
            if avg_trim > 10:
                symptoms["lean_running"] = True
            elif avg_trim < -10:
                symptoms["rich_running"] = True

        # Check for overheating
        coolant = [s.values.get("COOLANT_TEMP", 0) for s in session.pid_samples]
        if coolant and max(coolant) > 105:
            symptoms["overheating"] = True

        # Correlate symptoms to likely causes
        if symptoms["rough_idle"] and symptoms["lean_running"]:
            findings.append(self.create_finding(
                "Vacuum Leak Likely",
                "Combination of rough idle and lean running strongly suggests a vacuum leak.",
                severity="warning",
                category="diagnosis",
                confidence=0.85,
                recommendations=[
                    "Perform smoke test for vacuum leaks",
                    "Check intake manifold gaskets",
                    "Inspect vacuum hoses",
                    "Check PCV valve",
                ],
                related_pids=["RPM", "LONG_FUEL_TRIM_1"],
            ))

        if symptoms["rough_idle"] and symptoms["rich_running"]:
            findings.append(self.create_finding(
                "Fuel Injector Issue Likely",
                "Combination of rough idle and rich running suggests fuel injector problems.",
                severity="warning",
                category="diagnosis",
                confidence=0.7,
                recommendations=[
                    "Check for leaking fuel injectors",
                    "Clean fuel injectors",
                    "Check fuel pressure regulator",
                ],
                related_pids=["RPM", "LONG_FUEL_TRIM_1"],
            ))

        return findings
