"""DTC decoder for interpreting diagnostic trouble codes."""

import json
import logging
from pathlib import Path
from typing import Optional, Dict, List

from ..models.dtc import DTCInfo, DTCCategory, DTCSeverity

logger = logging.getLogger(__name__)


class DTCDecoder:
    """Decodes DTC codes into human-readable information."""

    def __init__(self, codes_file: Optional[Path] = None):
        """
        Initialize decoder with optional custom codes file.

        Args:
            codes_file: Path to JSON file with DTC codes database
        """
        self._codes_db: Dict[str, Dict] = {}
        self._loaded = False

        if codes_file:
            self._load_codes(codes_file)
        else:
            self._load_builtin_codes()

    def _load_codes(self, filepath: Path) -> None:
        """Load codes from JSON file."""
        try:
            with open(filepath, 'r') as f:
                self._codes_db = json.load(f)
            self._loaded = True
            logger.info(f"Loaded {len(self._codes_db)} DTC codes from {filepath}")
        except Exception as e:
            logger.warning(f"Failed to load DTC codes from {filepath}: {e}")
            self._load_builtin_codes()

    def _load_builtin_codes(self) -> None:
        """Load built-in common DTC codes."""
        # Try to load from package data directory
        data_dir = Path(__file__).parent.parent / "data"
        codes_file = data_dir / "dtc_codes.json"

        if codes_file.exists():
            self._load_codes(codes_file)
        else:
            # Use hardcoded common codes as fallback
            self._codes_db = COMMON_DTC_CODES
            self._loaded = True
            logger.debug("Using built-in DTC codes database")

    def decode(self, code: str) -> Optional[DTCInfo]:
        """
        Decode a DTC code into detailed information.

        Args:
            code: DTC code string (e.g., 'P0300')

        Returns:
            DTCInfo with decoded information
        """
        if not code:
            return None

        code = code.upper().strip()

        # Look up in database
        if code in self._codes_db:
            data = self._codes_db[code]
            return DTCInfo(
                code=code,
                description=data.get("description", "Unknown"),
                category=self._get_category(code),
                severity=self._parse_severity(data.get("severity", "warning")),
                possible_causes=data.get("causes", []),
                symptoms=data.get("symptoms", []),
                suggested_actions=data.get("actions", []),
            )

        # Generate basic info for unknown codes
        return DTCInfo.from_code(code)

    def get_description(self, code: str) -> str:
        """Get just the description for a code."""
        info = self.decode(code)
        return info.description if info else "Unknown code"

    def get_causes(self, code: str) -> List[str]:
        """Get possible causes for a code."""
        info = self.decode(code)
        return info.possible_causes if info else []

    def search(self, query: str) -> List[DTCInfo]:
        """
        Search codes by description.

        Args:
            query: Search string

        Returns:
            List of matching DTCInfo objects
        """
        query = query.lower()
        results = []

        for code, data in self._codes_db.items():
            desc = data.get("description", "").lower()
            if query in code.lower() or query in desc:
                info = self.decode(code)
                if info:
                    results.append(info)

        return results

    def get_codes_by_system(self, system_code: str) -> List[DTCInfo]:
        """
        Get all codes for a specific system.

        Args:
            system_code: System code (e.g., '3' for ignition)

        Returns:
            List of DTCInfo for that system
        """
        results = []
        for code in self._codes_db.keys():
            if len(code) >= 3 and code[2] == system_code:
                info = self.decode(code)
                if info:
                    results.append(info)
        return results

    @staticmethod
    def _get_category(code: str) -> DTCCategory:
        """Get category from code prefix."""
        if not code:
            return DTCCategory.POWERTRAIN

        prefix = code[0].upper()
        try:
            return DTCCategory(prefix)
        except ValueError:
            return DTCCategory.POWERTRAIN

    @staticmethod
    def _parse_severity(severity: str) -> DTCSeverity:
        """Parse severity string to enum."""
        severity = severity.lower()
        if severity == "critical":
            return DTCSeverity.CRITICAL
        elif severity == "warning":
            return DTCSeverity.WARNING
        else:
            return DTCSeverity.INFO


# Built-in common DTC codes database
COMMON_DTC_CODES = {
    # Misfires
    "P0300": {
        "description": "Random/Multiple Cylinder Misfire Detected",
        "severity": "critical",
        "causes": ["Faulty spark plugs", "Ignition coil failure", "Fuel injector issues", "Vacuum leak", "Low fuel pressure"],
        "symptoms": ["Rough idle", "Engine hesitation", "Check engine light flashing", "Reduced power"],
        "actions": ["Check spark plugs and wires", "Inspect ignition coils", "Check fuel pressure", "Inspect for vacuum leaks"]
    },
    "P0301": {
        "description": "Cylinder 1 Misfire Detected",
        "severity": "critical",
        "causes": ["Faulty spark plug cylinder 1", "Ignition coil failure", "Fuel injector issue", "Compression loss"],
        "symptoms": ["Rough idle", "Engine vibration", "Power loss"],
        "actions": ["Replace spark plug", "Test ignition coil", "Check fuel injector", "Perform compression test"]
    },
    "P0302": {"description": "Cylinder 2 Misfire Detected", "severity": "critical", "causes": ["Faulty spark plug", "Ignition coil"], "symptoms": ["Rough idle"], "actions": ["Replace spark plug"]},
    "P0303": {"description": "Cylinder 3 Misfire Detected", "severity": "critical", "causes": ["Faulty spark plug", "Ignition coil"], "symptoms": ["Rough idle"], "actions": ["Replace spark plug"]},
    "P0304": {"description": "Cylinder 4 Misfire Detected", "severity": "critical", "causes": ["Faulty spark plug", "Ignition coil"], "symptoms": ["Rough idle"], "actions": ["Replace spark plug"]},
    "P0305": {"description": "Cylinder 5 Misfire Detected", "severity": "critical", "causes": ["Faulty spark plug", "Ignition coil"], "symptoms": ["Rough idle"], "actions": ["Replace spark plug"]},
    "P0306": {"description": "Cylinder 6 Misfire Detected", "severity": "critical", "causes": ["Faulty spark plug", "Ignition coil"], "symptoms": ["Rough idle"], "actions": ["Replace spark plug"]},
    "P0307": {"description": "Cylinder 7 Misfire Detected", "severity": "critical", "causes": ["Faulty spark plug", "Ignition coil"], "symptoms": ["Rough idle"], "actions": ["Replace spark plug"]},
    "P0308": {"description": "Cylinder 8 Misfire Detected", "severity": "critical", "causes": ["Faulty spark plug", "Ignition coil"], "symptoms": ["Rough idle"], "actions": ["Replace spark plug"]},

    # Fuel System
    "P0171": {
        "description": "System Too Lean (Bank 1)",
        "severity": "warning",
        "causes": ["Vacuum leak", "Faulty MAF sensor", "Fuel pump weak", "Clogged fuel filter", "Faulty O2 sensor"],
        "symptoms": ["Poor fuel economy", "Rough idle", "Hesitation on acceleration"],
        "actions": ["Check for vacuum leaks", "Clean or replace MAF sensor", "Check fuel pressure"]
    },
    "P0172": {
        "description": "System Too Rich (Bank 1)",
        "severity": "warning",
        "causes": ["Faulty O2 sensor", "Leaking fuel injector", "High fuel pressure", "Faulty MAF sensor"],
        "symptoms": ["Black smoke from exhaust", "Poor fuel economy", "Rough idle"],
        "actions": ["Check O2 sensor", "Test fuel injectors", "Check fuel pressure regulator"]
    },
    "P0174": {"description": "System Too Lean (Bank 2)", "severity": "warning", "causes": ["Vacuum leak", "MAF sensor"], "symptoms": ["Poor fuel economy"], "actions": ["Check for vacuum leaks"]},
    "P0175": {"description": "System Too Rich (Bank 2)", "severity": "warning", "causes": ["O2 sensor", "Fuel injector"], "symptoms": ["Black smoke"], "actions": ["Check O2 sensor"]},

    # O2 Sensors
    "P0130": {"description": "O2 Sensor Circuit (Bank 1 Sensor 1)", "severity": "warning", "causes": ["Faulty O2 sensor", "Wiring issue"], "symptoms": ["Poor fuel economy"], "actions": ["Replace O2 sensor"]},
    "P0131": {"description": "O2 Sensor Low Voltage (Bank 1 Sensor 1)", "severity": "warning", "causes": ["Lean condition", "Faulty sensor"], "symptoms": ["Check engine light"], "actions": ["Check for leaks", "Replace sensor"]},
    "P0132": {"description": "O2 Sensor High Voltage (Bank 1 Sensor 1)", "severity": "warning", "causes": ["Rich condition", "Faulty sensor"], "symptoms": ["Check engine light"], "actions": ["Check fuel system"]},
    "P0133": {"description": "O2 Sensor Slow Response (Bank 1 Sensor 1)", "severity": "warning", "causes": ["Aging sensor", "Contamination"], "symptoms": ["Poor fuel economy"], "actions": ["Replace O2 sensor"]},
    "P0134": {"description": "O2 Sensor No Activity (Bank 1 Sensor 1)", "severity": "warning", "causes": ["Faulty sensor", "Wiring"], "symptoms": ["Check engine light"], "actions": ["Check wiring", "Replace sensor"]},

    # Catalyst
    "P0420": {
        "description": "Catalyst System Efficiency Below Threshold (Bank 1)",
        "severity": "warning",
        "causes": ["Worn catalytic converter", "Faulty O2 sensor", "Exhaust leak", "Engine misfire damage"],
        "symptoms": ["Check engine light", "Reduced fuel economy", "Failed emissions test"],
        "actions": ["Check O2 sensors first", "Inspect exhaust for leaks", "Consider catalyst replacement"]
    },
    "P0430": {"description": "Catalyst System Efficiency Below Threshold (Bank 2)", "severity": "warning", "causes": ["Worn catalytic converter"], "symptoms": ["Check engine light"], "actions": ["Check O2 sensors"]},

    # EVAP System
    "P0440": {"description": "EVAP System Malfunction", "severity": "info", "causes": ["Loose gas cap", "EVAP leak"], "symptoms": ["Check engine light"], "actions": ["Tighten gas cap", "Check EVAP system"]},
    "P0441": {"description": "EVAP Incorrect Purge Flow", "severity": "info", "causes": ["Purge valve stuck", "Vacuum leak"], "symptoms": ["Check engine light"], "actions": ["Check purge valve"]},
    "P0442": {"description": "EVAP Small Leak Detected", "severity": "info", "causes": ["Small leak in EVAP system", "Gas cap"], "symptoms": ["Check engine light"], "actions": ["Check gas cap seal", "Smoke test EVAP system"]},
    "P0446": {"description": "EVAP Vent System Performance", "severity": "info", "causes": ["Vent valve stuck", "Blocked vent"], "symptoms": ["Check engine light"], "actions": ["Check vent valve"]},
    "P0455": {"description": "EVAP Large Leak Detected", "severity": "warning", "causes": ["Missing gas cap", "Large EVAP leak"], "symptoms": ["Check engine light", "Fuel smell"], "actions": ["Check gas cap", "Inspect EVAP hoses"]},

    # EGR
    "P0400": {"description": "EGR Flow Malfunction", "severity": "warning", "causes": ["Clogged EGR valve", "EGR passages blocked"], "symptoms": ["Rough idle", "Knocking"], "actions": ["Clean or replace EGR valve"]},
    "P0401": {"description": "EGR Insufficient Flow", "severity": "warning", "causes": ["Carbon buildup", "EGR valve stuck closed"], "symptoms": ["Knocking on acceleration"], "actions": ["Clean EGR passages"]},
    "P0402": {"description": "EGR Excessive Flow", "severity": "warning", "causes": ["EGR valve stuck open", "Vacuum leak"], "symptoms": ["Rough idle", "Stalling"], "actions": ["Replace EGR valve"]},

    # MAF Sensor
    "P0100": {"description": "MAF Sensor Circuit", "severity": "warning", "causes": ["Faulty MAF sensor", "Wiring issue"], "symptoms": ["Poor performance"], "actions": ["Check MAF sensor and wiring"]},
    "P0101": {"description": "MAF Sensor Range/Performance", "severity": "warning", "causes": ["Dirty MAF sensor", "Air leak"], "symptoms": ["Rough idle", "Hesitation"], "actions": ["Clean MAF sensor", "Check for air leaks"]},
    "P0102": {"description": "MAF Sensor Low Input", "severity": "warning", "causes": ["Dirty sensor", "Wiring short"], "symptoms": ["Rich running"], "actions": ["Clean or replace MAF"]},
    "P0103": {"description": "MAF Sensor High Input", "severity": "warning", "causes": ["Sensor failure", "Wiring issue"], "symptoms": ["Lean running"], "actions": ["Check wiring", "Replace MAF"]},

    # Throttle Position
    "P0120": {"description": "Throttle Position Sensor Circuit", "severity": "warning", "causes": ["Faulty TPS", "Wiring"], "symptoms": ["Erratic idle"], "actions": ["Check TPS and wiring"]},
    "P0121": {"description": "TPS Range/Performance", "severity": "warning", "causes": ["Worn TPS", "Throttle body issue"], "symptoms": ["Hesitation", "Stalling"], "actions": ["Replace TPS"]},
    "P0122": {"description": "TPS Low Input", "severity": "warning", "causes": ["Sensor failure", "Wiring short"], "symptoms": ["No throttle response"], "actions": ["Check wiring", "Replace TPS"]},
    "P0123": {"description": "TPS High Input", "severity": "warning", "causes": ["Sensor failure", "Wiring short to power"], "symptoms": ["High idle"], "actions": ["Check wiring", "Replace TPS"]},

    # Coolant Temperature
    "P0115": {"description": "Engine Coolant Temperature Sensor Circuit", "severity": "warning", "causes": ["Faulty sensor", "Wiring"], "symptoms": ["Wrong temp reading"], "actions": ["Check sensor and wiring"]},
    "P0116": {"description": "ECT Sensor Range/Performance", "severity": "warning", "causes": ["Thermostat stuck", "Sensor issue"], "symptoms": ["Poor fuel economy"], "actions": ["Check thermostat", "Replace sensor"]},
    "P0117": {"description": "ECT Sensor Low Input", "severity": "warning", "causes": ["Short circuit", "Sensor failure"], "symptoms": ["Always shows hot"], "actions": ["Check wiring"]},
    "P0118": {"description": "ECT Sensor High Input", "severity": "warning", "causes": ["Open circuit", "Sensor failure"], "symptoms": ["Always shows cold"], "actions": ["Check wiring"]},

    # Crankshaft/Camshaft
    "P0335": {"description": "Crankshaft Position Sensor Circuit", "severity": "critical", "causes": ["Faulty sensor", "Wiring", "Timing issue"], "symptoms": ["No start", "Stalling"], "actions": ["Check sensor", "Check timing belt/chain"]},
    "P0336": {"description": "Crankshaft Position Sensor Range/Performance", "severity": "critical", "causes": ["Sensor gap", "Reluctor wheel damage"], "symptoms": ["Rough running"], "actions": ["Check sensor gap"]},
    "P0340": {"description": "Camshaft Position Sensor Circuit", "severity": "critical", "causes": ["Faulty sensor", "Wiring"], "symptoms": ["No start", "Rough idle"], "actions": ["Check sensor and wiring"]},
    "P0341": {"description": "Camshaft Position Sensor Range/Performance", "severity": "critical", "causes": ["Timing issue", "Sensor failure"], "symptoms": ["Rough running"], "actions": ["Check timing", "Replace sensor"]},

    # Knock Sensor
    "P0325": {"description": "Knock Sensor 1 Circuit", "severity": "warning", "causes": ["Faulty sensor", "Wiring"], "symptoms": ["Reduced power", "Knocking"], "actions": ["Check sensor"]},
    "P0330": {"description": "Knock Sensor 2 Circuit", "severity": "warning", "causes": ["Faulty sensor", "Wiring"], "symptoms": ["Reduced power"], "actions": ["Check sensor"]},

    # Transmission
    "P0700": {"description": "Transmission Control System Malfunction", "severity": "warning", "causes": ["TCM issue", "Wiring"], "symptoms": ["Transmission problems"], "actions": ["Scan transmission codes"]},
    "P0715": {"description": "Input/Turbine Speed Sensor Circuit", "severity": "warning", "causes": ["Faulty sensor", "Wiring"], "symptoms": ["Harsh shifts"], "actions": ["Check sensor"]},
    "P0720": {"description": "Output Speed Sensor Circuit", "severity": "warning", "causes": ["Faulty sensor", "Wiring"], "symptoms": ["Speedometer issues", "Shift problems"], "actions": ["Check sensor"]},
    "P0730": {"description": "Incorrect Gear Ratio", "severity": "critical", "causes": ["Worn clutches", "Low fluid", "Valve body"], "symptoms": ["Slipping", "Harsh shifts"], "actions": ["Check fluid", "Professional diagnosis"]},
    "P0741": {"description": "Torque Converter Clutch Solenoid Performance", "severity": "warning", "causes": ["Solenoid failure", "Wiring"], "symptoms": ["Poor fuel economy", "Shudder"], "actions": ["Check solenoid"]},

    # Fuel Injectors
    "P0200": {"description": "Fuel Injector Circuit", "severity": "warning", "causes": ["Injector failure", "Wiring"], "symptoms": ["Rough running"], "actions": ["Check injectors"]},
    "P0201": {"description": "Injector Circuit - Cylinder 1", "severity": "warning", "causes": ["Faulty injector", "Wiring"], "symptoms": ["Misfire cyl 1"], "actions": ["Check injector 1"]},
    "P0202": {"description": "Injector Circuit - Cylinder 2", "severity": "warning", "causes": ["Faulty injector"], "symptoms": ["Misfire cyl 2"], "actions": ["Check injector 2"]},
    "P0203": {"description": "Injector Circuit - Cylinder 3", "severity": "warning", "causes": ["Faulty injector"], "symptoms": ["Misfire cyl 3"], "actions": ["Check injector 3"]},
    "P0204": {"description": "Injector Circuit - Cylinder 4", "severity": "warning", "causes": ["Faulty injector"], "symptoms": ["Misfire cyl 4"], "actions": ["Check injector 4"]},

    # Fuel Pressure
    "P0190": {"description": "Fuel Rail Pressure Sensor Circuit", "severity": "warning", "causes": ["Sensor failure", "Wiring"], "symptoms": ["Running issues"], "actions": ["Check sensor"]},
    "P0191": {"description": "Fuel Rail Pressure Sensor Range/Performance", "severity": "warning", "causes": ["Fuel pressure issue", "Sensor"], "symptoms": ["Poor performance"], "actions": ["Check fuel pressure"]},

    # Oxygen Sensor Heater
    "P0135": {"description": "O2 Sensor Heater Circuit (Bank 1 Sensor 1)", "severity": "info", "causes": ["Heater element failed", "Wiring"], "symptoms": ["Slow warmup"], "actions": ["Replace O2 sensor"]},
    "P0141": {"description": "O2 Sensor Heater Circuit (Bank 1 Sensor 2)", "severity": "info", "causes": ["Heater element failed"], "symptoms": ["Check engine light"], "actions": ["Replace O2 sensor"]},
    "P0155": {"description": "O2 Sensor Heater Circuit (Bank 2 Sensor 1)", "severity": "info", "causes": ["Heater element failed"], "symptoms": ["Check engine light"], "actions": ["Replace O2 sensor"]},
    "P0161": {"description": "O2 Sensor Heater Circuit (Bank 2 Sensor 2)", "severity": "info", "causes": ["Heater element failed"], "symptoms": ["Check engine light"], "actions": ["Replace O2 sensor"]},
}
