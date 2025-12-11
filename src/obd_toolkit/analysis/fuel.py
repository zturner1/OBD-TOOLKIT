"""Fuel economy analyzer."""

from typing import List, Tuple
import statistics

from .base import BaseAnalyzer
from ..models.session import DiagnosticSession, AnalysisResult, AnalysisFinding


class FuelEconomyAnalyzer(BaseAnalyzer):
    """Analyzes fuel economy patterns and efficiency."""

    @property
    def name(self) -> str:
        return "Fuel Economy Analysis"

    @property
    def description(self) -> str:
        return "Analyzes fuel consumption patterns and identifies inefficiencies"

    def get_required_pids(self) -> List[str]:
        return ["MAF", "SPEED", "RPM", "ENGINE_LOAD"]

    def analyze(self, session: DiagnosticSession) -> AnalysisResult:
        """Analyze fuel economy data."""
        findings = []
        metrics = {}

        if not session.pid_samples:
            return self.create_result(
                findings=[self.create_finding(
                    "No Data",
                    "No PID samples available for analysis",
                    severity="info"
                )],
                summary="Insufficient data for fuel analysis"
            )

        # Extract time series data
        maf_values = []
        speed_values = []
        rpm_values = []
        load_values = []

        for sample in session.pid_samples:
            if "MAF" in sample.values:
                maf_values.append(sample.values["MAF"])
            if "SPEED" in sample.values:
                speed_values.append(sample.values["SPEED"])
            if "RPM" in sample.values:
                rpm_values.append(sample.values["RPM"])
            if "ENGINE_LOAD" in sample.values:
                load_values.append(sample.values["ENGINE_LOAD"])

        # Calculate fuel economy if we have MAF and speed
        if maf_values and speed_values:
            mpg_samples = self._calculate_mpg_series(maf_values, speed_values)

            if mpg_samples:
                metrics["average_mpg"] = statistics.mean(mpg_samples)
                metrics["max_mpg"] = max(mpg_samples)
                metrics["min_mpg"] = min(mpg_samples)

                # Analyze fuel economy patterns
                findings.extend(self._analyze_mpg_patterns(mpg_samples, speed_values))

        # Analyze fuel consumption patterns
        if maf_values:
            metrics["avg_maf"] = statistics.mean(maf_values)
            findings.extend(self._analyze_maf_patterns(maf_values, rpm_values))

        # Analyze idle fuel consumption
        if maf_values and rpm_values:
            findings.extend(self._analyze_idle_fuel(maf_values, rpm_values))

        # Analyze driving patterns for efficiency
        if speed_values and rpm_values:
            findings.extend(self._analyze_driving_efficiency(speed_values, rpm_values))

        # Analyze acceleration patterns
        if speed_values:
            findings.extend(self._analyze_acceleration(speed_values))

        # Generate summary
        if "average_mpg" in metrics:
            summary = f"Average fuel economy: {metrics['average_mpg']:.1f} MPG. "
            if metrics['average_mpg'] < 15:
                summary += "Below average efficiency - see recommendations."
            elif metrics['average_mpg'] > 30:
                summary += "Good fuel efficiency."
            else:
                summary += "Moderate fuel efficiency."
        else:
            summary = "Fuel economy could not be calculated. Ensure MAF and SPEED data is available."

        return self.create_result(findings=findings, summary=summary, metrics=metrics)

    def _calculate_mpg_series(
        self,
        maf_values: List[float],
        speed_values: List[float]
    ) -> List[float]:
        """Calculate MPG for each sample."""
        mpg_values = []

        min_len = min(len(maf_values), len(speed_values))

        for i in range(min_len):
            maf = maf_values[i]
            speed = speed_values[i]

            # Skip if stationary or no airflow
            if speed < 5 or maf < 0.5:
                continue

            # MPG calculation: (speed * 7.718) / MAF
            # This assumes gasoline with AFR of 14.7
            mpg = (speed * 7.718) / maf
            mpg = speed * 0.621371 * 7.718 / maf  # Convert km/h to mph first

            # Sanity check - ignore unrealistic values
            if 1 < mpg < 100:
                mpg_values.append(mpg)

        return mpg_values

    def _analyze_mpg_patterns(
        self,
        mpg_values: List[float],
        speed_values: List[float]
    ) -> List[AnalysisFinding]:
        """Analyze MPG patterns."""
        findings = []

        if len(mpg_values) < 5:
            return findings

        avg_mpg = statistics.mean(mpg_values)
        std_mpg = statistics.stdev(mpg_values) if len(mpg_values) > 1 else 0

        # Check for poor fuel economy
        if avg_mpg < 15:
            findings.append(self.create_finding(
                "Poor Fuel Economy",
                f"Average fuel economy is {avg_mpg:.1f} MPG, which is below typical values. "
                "This may indicate engine or driving efficiency issues.",
                severity="warning",
                category="fuel",
                confidence=0.7,
                recommendations=[
                    "Check for dragging brakes",
                    "Verify tire pressure",
                    "Check air filter",
                    "Consider driving habit adjustments",
                    "Check for engine issues (misfires, O2 sensors)",
                ],
                related_pids=["MAF", "SPEED"],
            ))

        # Check for high MPG variance
        if std_mpg > 10:
            findings.append(self.create_finding(
                "Inconsistent Fuel Economy",
                f"Fuel economy varies significantly ({std_mpg:.1f} MPG std). "
                "This suggests varied driving conditions or engine inconsistency.",
                severity="info",
                category="fuel",
                confidence=0.6,
                related_pids=["MAF", "SPEED"],
            ))

        return findings

    def _analyze_maf_patterns(
        self,
        maf_values: List[float],
        rpm_values: List[float]
    ) -> List[AnalysisFinding]:
        """Analyze MAF patterns for issues."""
        findings = []

        if len(maf_values) < 5:
            return findings

        avg_maf = statistics.mean(maf_values)
        max_maf = max(maf_values)

        # Check for unusually high airflow
        if max_maf > 200:
            findings.append(self.create_finding(
                "High Airflow Detected",
                f"Maximum MAF reading of {max_maf:.1f} g/s detected. "
                "Verify this matches expected engine performance.",
                severity="info",
                category="fuel",
                related_pids=["MAF"],
            ))

        # Check MAF vs RPM correlation if we have RPM data
        if rpm_values and len(rpm_values) == len(maf_values):
            # At idle (low RPM), MAF should be low
            idle_maf = [maf_values[i] for i in range(len(rpm_values)) if rpm_values[i] < 1000]

            if idle_maf and statistics.mean(idle_maf) > 10:
                findings.append(self.create_finding(
                    "High Idle Airflow",
                    f"MAF at idle is higher than expected ({statistics.mean(idle_maf):.1f} g/s). "
                    "This may indicate a vacuum leak or MAF sensor issue.",
                    severity="warning",
                    category="fuel",
                    confidence=0.6,
                    recommendations=[
                        "Check for vacuum leaks",
                        "Clean MAF sensor",
                        "Check intake system for leaks",
                    ],
                    related_pids=["MAF", "RPM"],
                ))

        return findings

    def _analyze_idle_fuel(
        self,
        maf_values: List[float],
        rpm_values: List[float]
    ) -> List[AnalysisFinding]:
        """Analyze fuel consumption at idle."""
        findings = []

        # Find idle periods
        idle_maf = []
        for i in range(len(rpm_values)):
            if i < len(maf_values) and rpm_values[i] < 1000:
                idle_maf.append(maf_values[i])

        if len(idle_maf) < 3:
            return findings

        avg_idle_maf = statistics.mean(idle_maf)

        # Estimate idle fuel consumption (L/h)
        # Assuming gasoline: fuel_rate = MAF / (AFR * density) = MAF / (14.7 * 750) * 3600
        idle_fuel_lph = (avg_idle_maf * 3600) / (14.7 * 750)

        if idle_fuel_lph > 2.0:
            findings.append(self.create_finding(
                "High Idle Fuel Consumption",
                f"Estimated idle fuel consumption is {idle_fuel_lph:.1f} L/h. "
                "This is higher than typical for most vehicles.",
                severity="info",
                category="fuel",
                confidence=0.5,
                recommendations=[
                    "Check for accessories consuming power",
                    "Verify engine is at operating temperature",
                    "Check for vacuum leaks",
                ],
                related_pids=["MAF", "RPM"],
            ))

        return findings

    def _analyze_driving_efficiency(
        self,
        speed_values: List[float],
        rpm_values: List[float]
    ) -> List[AnalysisFinding]:
        """Analyze driving efficiency based on speed/RPM relationship."""
        findings = []

        if len(speed_values) < 10 or len(rpm_values) < 10:
            return findings

        # Calculate speed/RPM ratio (gear indicator)
        min_len = min(len(speed_values), len(rpm_values))
        ratios = []

        for i in range(min_len):
            if rpm_values[i] > 500 and speed_values[i] > 20:
                ratio = speed_values[i] / rpm_values[i] * 1000
                ratios.append(ratio)

        if not ratios:
            return findings

        avg_ratio = statistics.mean(ratios)

        # Low ratio means high RPM for speed (possibly wrong gear)
        if avg_ratio < 20:
            findings.append(self.create_finding(
                "High RPM Driving Pattern",
                "Vehicle is being driven at higher RPMs than necessary for the speed. "
                "This reduces fuel economy.",
                severity="info",
                category="driving",
                confidence=0.6,
                recommendations=[
                    "Shift to higher gear sooner",
                    "Use eco/economy mode if available",
                    "Accelerate more gradually",
                ],
                related_pids=["SPEED", "RPM"],
            ))

        return findings

    def _analyze_acceleration(self, speed_values: List[float]) -> List[AnalysisFinding]:
        """Analyze acceleration patterns."""
        findings = []

        if len(speed_values) < 10:
            return findings

        # Calculate acceleration between samples
        accelerations = []
        for i in range(1, len(speed_values)):
            accel = speed_values[i] - speed_values[i-1]
            accelerations.append(accel)

        if not accelerations:
            return findings

        # Count aggressive accelerations (>10 km/h change per sample)
        aggressive_accels = [a for a in accelerations if a > 10]

        if len(aggressive_accels) > len(accelerations) * 0.2:  # More than 20% aggressive
            findings.append(self.create_finding(
                "Aggressive Acceleration Pattern",
                f"Detected frequent rapid acceleration ({len(aggressive_accels)} instances). "
                "This significantly impacts fuel economy.",
                severity="info",
                category="driving",
                confidence=0.7,
                recommendations=[
                    "Accelerate more gradually",
                    "Anticipate traffic to avoid sudden acceleration",
                    "Use cruise control when possible",
                ],
                related_pids=["SPEED"],
            ))

        # Check for excessive idling (speed near 0 for long periods)
        idle_count = sum(1 for s in speed_values if s < 5)
        if idle_count > len(speed_values) * 0.3:  # More than 30% idle
            findings.append(self.create_finding(
                "Excessive Idling Detected",
                f"Vehicle was stationary for {idle_count / len(speed_values) * 100:.0f}% of the monitoring period. "
                "Idling wastes fuel.",
                severity="info",
                category="driving",
                confidence=0.8,
                recommendations=[
                    "Turn off engine during extended stops",
                    "Use auto start-stop if equipped",
                    "Plan routes to minimize stop-and-go traffic",
                ],
                related_pids=["SPEED"],
            ))

        return findings
