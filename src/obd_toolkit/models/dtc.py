"""Data models for Diagnostic Trouble Codes (DTCs)."""

from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime


class DTCCategory(str, Enum):
    """DTC category based on first character."""
    POWERTRAIN = "P"  # Engine, transmission
    BODY = "B"        # Body systems (AC, airbag, etc.)
    CHASSIS = "C"     # ABS, steering, suspension
    NETWORK = "U"     # Communication/network


class DTCSeverity(str, Enum):
    """Severity level of DTC."""
    CRITICAL = "critical"    # Immediate attention needed
    WARNING = "warning"      # Should be addressed soon
    INFO = "info"            # Minor issue or informational


class DTCType(str, Enum):
    """Type of DTC storage."""
    STORED = "stored"        # Currently active (Mode 03)
    PENDING = "pending"      # Detected but not confirmed (Mode 07)
    PERMANENT = "permanent"  # Cannot be cleared without repair (Mode 0A)


class DTCInfo(BaseModel):
    """Complete information about a Diagnostic Trouble Code."""

    code: str = Field(..., description="DTC code (e.g., P0300)")
    description: str = Field(default="Unknown code", description="Human-readable description")
    category: DTCCategory = Field(..., description="Code category (P/B/C/U)")
    severity: DTCSeverity = Field(default=DTCSeverity.WARNING, description="Severity level")
    dtc_type: DTCType = Field(default=DTCType.STORED, description="Type of DTC")

    possible_causes: List[str] = Field(default_factory=list, description="Possible causes")
    symptoms: List[str] = Field(default_factory=list, description="Common symptoms")
    suggested_actions: List[str] = Field(default_factory=list, description="Recommended actions")

    freeze_frame: Optional[dict] = Field(default=None, description="Freeze frame data if available")
    timestamp: datetime = Field(default_factory=datetime.now, description="When this DTC was read")

    @classmethod
    def from_code(cls, code: str, description: str = "Unknown", dtc_type: DTCType = DTCType.STORED) -> "DTCInfo":
        """Create DTCInfo from a code string."""
        if not code or len(code) < 2:
            raise ValueError(f"Invalid DTC code: {code}")

        category_char = code[0].upper()
        try:
            category = DTCCategory(category_char)
        except ValueError:
            category = DTCCategory.POWERTRAIN

        # Determine severity based on code patterns
        severity = cls._determine_severity(code)

        return cls(
            code=code.upper(),
            description=description,
            category=category,
            severity=severity,
            dtc_type=dtc_type,
        )

    @staticmethod
    def _determine_severity(code: str) -> DTCSeverity:
        """Determine severity based on code patterns."""
        code = code.upper()

        # Critical codes - misfires, catalyst damage, major failures
        critical_patterns = ["P0300", "P0301", "P0302", "P0303", "P0304",
                           "P0305", "P0306", "P0307", "P0308",  # Misfires
                           "P0217", "P0218",  # Overheating
                           "P0520", "P0521",  # Oil pressure
                           ]

        if any(code.startswith(p) for p in critical_patterns):
            return DTCSeverity.CRITICAL

        # Warning codes - emissions, sensors, moderate issues
        warning_patterns = ["P04", "P01", "P02", "P03"]
        if any(code.startswith(p) for p in warning_patterns):
            return DTCSeverity.WARNING

        return DTCSeverity.INFO

    @property
    def is_generic(self) -> bool:
        """Check if this is a generic (SAE) code vs manufacturer-specific."""
        if len(self.code) < 2:
            return True
        second_char = self.code[1]
        return second_char in ("0", "2")  # P0xxx and P2xxx are generic

    @property
    def system(self) -> str:
        """Get the system this code relates to."""
        if len(self.code) < 3:
            return "Unknown"

        third_char = self.code[2]
        systems = {
            "1": "Fuel and Air Metering",
            "2": "Fuel and Air Metering (Injector Circuit)",
            "3": "Ignition System or Misfire",
            "4": "Auxiliary Emissions Controls",
            "5": "Vehicle Speed Controls and Idle Control System",
            "6": "Computer Output Circuit",
            "7": "Transmission",
            "8": "Transmission",
        }
        return systems.get(third_char, "Unknown System")

    def __str__(self) -> str:
        return f"{self.code}: {self.description}"


class DTCReadResult(BaseModel):
    """Result of reading DTCs from a vehicle."""

    stored_codes: List[DTCInfo] = Field(default_factory=list)
    pending_codes: List[DTCInfo] = Field(default_factory=list)
    permanent_codes: List[DTCInfo] = Field(default_factory=list)

    mil_status: bool = Field(default=False, description="Malfunction Indicator Lamp status")
    dtc_count: int = Field(default=0, description="Total number of DTCs reported by ECU")

    timestamp: datetime = Field(default_factory=datetime.now)

    @property
    def total_codes(self) -> int:
        """Total number of codes across all types."""
        return len(self.stored_codes) + len(self.pending_codes) + len(self.permanent_codes)

    @property
    def has_critical(self) -> bool:
        """Check if any critical codes are present."""
        all_codes = self.stored_codes + self.pending_codes + self.permanent_codes
        return any(dtc.severity == DTCSeverity.CRITICAL for dtc in all_codes)

    @property
    def all_codes(self) -> List[DTCInfo]:
        """Get all codes as a single list."""
        return self.stored_codes + self.pending_codes + self.permanent_codes
