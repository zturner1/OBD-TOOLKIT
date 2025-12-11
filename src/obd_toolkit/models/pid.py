"""Data models for Parameter IDs (PIDs)."""

from typing import Optional, Any, Union
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class PIDUnit(str, Enum):
    """Common units for PID values."""
    # Speed
    KPH = "km/h"
    MPH = "mph"

    # Temperature
    CELSIUS = "C"
    FAHRENHEIT = "F"

    # Pressure
    KPA = "kPa"
    PSI = "psi"
    INHG = "inHg"

    # Flow
    GPS = "g/s"  # grams per second
    LPH = "L/h"  # liters per hour

    # Electrical
    VOLTS = "V"
    MILLIAMPS = "mA"

    # Engine
    RPM = "rpm"
    PERCENT = "%"
    DEGREES = "deg"
    SECONDS = "s"

    # Fuel
    RATIO = "ratio"

    # Generic
    COUNT = "count"
    NONE = ""


class PIDInfo(BaseModel):
    """Information about a PID definition."""

    pid: str = Field(..., description="PID identifier (e.g., 'RPM', 'SPEED')")
    name: str = Field(..., description="Human-readable name")
    description: str = Field(default="", description="Detailed description")
    unit: PIDUnit = Field(default=PIDUnit.NONE, description="Unit of measurement")

    min_value: Optional[float] = Field(default=None, description="Minimum possible value")
    max_value: Optional[float] = Field(default=None, description="Maximum possible value")

    mode: int = Field(default=1, description="OBD mode (1 = live data)")
    command_code: Optional[str] = Field(default=None, description="Raw hex command code")

    is_supported: bool = Field(default=False, description="Whether vehicle supports this PID")


class PIDValue(BaseModel):
    """A single PID reading with value and metadata."""

    pid: str = Field(..., description="PID identifier")
    name: str = Field(..., description="Human-readable name")
    value: Optional[Union[float, int, str, bool]] = Field(default=None, description="The value")
    unit: str = Field(default="", description="Unit of measurement")

    raw_value: Optional[bytes] = Field(default=None, description="Raw bytes from ECU")
    timestamp: datetime = Field(default_factory=datetime.now, description="When value was read")

    is_valid: bool = Field(default=True, description="Whether the reading is valid")
    error_message: Optional[str] = Field(default=None, description="Error if invalid")

    @property
    def formatted_value(self) -> str:
        """Get formatted value with unit."""
        if self.value is None:
            return "N/A"
        if isinstance(self.value, float):
            return f"{self.value:.2f} {self.unit}".strip()
        return f"{self.value} {self.unit}".strip()

    @property
    def numeric_value(self) -> Optional[float]:
        """Get value as float if possible."""
        if self.value is None:
            return None
        if isinstance(self.value, (int, float)):
            return float(self.value)
        return None


class PIDSnapshot(BaseModel):
    """A snapshot of multiple PID values at a point in time."""

    timestamp: datetime = Field(default_factory=datetime.now)
    values: dict[str, PIDValue] = Field(default_factory=dict)

    def get(self, pid: str) -> Optional[PIDValue]:
        """Get a PID value by name."""
        return self.values.get(pid)

    def get_value(self, pid: str) -> Optional[Union[float, int, str, bool]]:
        """Get just the value for a PID."""
        pv = self.values.get(pid)
        return pv.value if pv else None


# Common PID definitions
COMMON_PIDS = {
    "RPM": PIDInfo(
        pid="RPM",
        name="Engine RPM",
        description="Engine revolutions per minute",
        unit=PIDUnit.RPM,
        min_value=0,
        max_value=16383.75,
        command_code="010C"
    ),
    "SPEED": PIDInfo(
        pid="SPEED",
        name="Vehicle Speed",
        description="Current vehicle speed",
        unit=PIDUnit.KPH,
        min_value=0,
        max_value=255,
        command_code="010D"
    ),
    "COOLANT_TEMP": PIDInfo(
        pid="COOLANT_TEMP",
        name="Engine Coolant Temperature",
        description="Temperature of engine coolant",
        unit=PIDUnit.CELSIUS,
        min_value=-40,
        max_value=215,
        command_code="0105"
    ),
    "ENGINE_LOAD": PIDInfo(
        pid="ENGINE_LOAD",
        name="Calculated Engine Load",
        description="Calculated engine load value",
        unit=PIDUnit.PERCENT,
        min_value=0,
        max_value=100,
        command_code="0104"
    ),
    "THROTTLE_POS": PIDInfo(
        pid="THROTTLE_POS",
        name="Throttle Position",
        description="Throttle position sensor value",
        unit=PIDUnit.PERCENT,
        min_value=0,
        max_value=100,
        command_code="0111"
    ),
    "INTAKE_TEMP": PIDInfo(
        pid="INTAKE_TEMP",
        name="Intake Air Temperature",
        description="Temperature of intake air",
        unit=PIDUnit.CELSIUS,
        min_value=-40,
        max_value=215,
        command_code="010F"
    ),
    "MAF": PIDInfo(
        pid="MAF",
        name="Mass Air Flow Rate",
        description="Mass air flow sensor reading",
        unit=PIDUnit.GPS,
        min_value=0,
        max_value=655.35,
        command_code="0110"
    ),
    "FUEL_PRESSURE": PIDInfo(
        pid="FUEL_PRESSURE",
        name="Fuel Pressure",
        description="Fuel system pressure",
        unit=PIDUnit.KPA,
        min_value=0,
        max_value=765,
        command_code="010A"
    ),
    "TIMING_ADVANCE": PIDInfo(
        pid="TIMING_ADVANCE",
        name="Timing Advance",
        description="Ignition timing advance",
        unit=PIDUnit.DEGREES,
        min_value=-64,
        max_value=63.5,
        command_code="010E"
    ),
    "SHORT_FUEL_TRIM_1": PIDInfo(
        pid="SHORT_FUEL_TRIM_1",
        name="Short Term Fuel Trim - Bank 1",
        description="Short term fuel trim for bank 1",
        unit=PIDUnit.PERCENT,
        min_value=-100,
        max_value=99.2,
        command_code="0106"
    ),
    "LONG_FUEL_TRIM_1": PIDInfo(
        pid="LONG_FUEL_TRIM_1",
        name="Long Term Fuel Trim - Bank 1",
        description="Long term fuel trim for bank 1",
        unit=PIDUnit.PERCENT,
        min_value=-100,
        max_value=99.2,
        command_code="0107"
    ),
    "O2_B1S1": PIDInfo(
        pid="O2_B1S1",
        name="O2 Sensor Bank 1 Sensor 1",
        description="Oxygen sensor voltage",
        unit=PIDUnit.VOLTS,
        min_value=0,
        max_value=1.275,
        command_code="0114"
    ),
    "FUEL_STATUS": PIDInfo(
        pid="FUEL_STATUS",
        name="Fuel System Status",
        description="Current fuel system status",
        unit=PIDUnit.NONE,
        command_code="0103"
    ),
    "RUN_TIME": PIDInfo(
        pid="RUN_TIME",
        name="Engine Run Time",
        description="Time since engine start",
        unit=PIDUnit.SECONDS,
        min_value=0,
        max_value=65535,
        command_code="011F"
    ),
    "DISTANCE_W_MIL": PIDInfo(
        pid="DISTANCE_W_MIL",
        name="Distance with MIL",
        description="Distance traveled with MIL on",
        unit=PIDUnit.KPH,  # Actually km, but using same type
        min_value=0,
        max_value=65535,
        command_code="0121"
    ),
    "BAROMETRIC_PRESSURE": PIDInfo(
        pid="BAROMETRIC_PRESSURE",
        name="Barometric Pressure",
        description="Absolute barometric pressure",
        unit=PIDUnit.KPA,
        min_value=0,
        max_value=255,
        command_code="0133"
    ),
    "CONTROL_MODULE_VOLTAGE": PIDInfo(
        pid="CONTROL_MODULE_VOLTAGE",
        name="Control Module Voltage",
        description="ECU supply voltage",
        unit=PIDUnit.VOLTS,
        min_value=0,
        max_value=65.535,
        command_code="0142"
    ),
    "AMBIENT_AIR_TEMP": PIDInfo(
        pid="AMBIENT_AIR_TEMP",
        name="Ambient Air Temperature",
        description="Outside air temperature",
        unit=PIDUnit.CELSIUS,
        min_value=-40,
        max_value=215,
        command_code="0146"
    ),
    "FUEL_LEVEL": PIDInfo(
        pid="FUEL_LEVEL",
        name="Fuel Level Input",
        description="Fuel tank level",
        unit=PIDUnit.PERCENT,
        min_value=0,
        max_value=100,
        command_code="012F"
    ),
}


# PID presets for common monitoring scenarios
PID_PRESETS = {
    "engine": ["RPM", "ENGINE_LOAD", "COOLANT_TEMP", "THROTTLE_POS", "TIMING_ADVANCE"],
    "fuel": ["MAF", "FUEL_PRESSURE", "SHORT_FUEL_TRIM_1", "LONG_FUEL_TRIM_1", "FUEL_LEVEL"],
    "sensors": ["COOLANT_TEMP", "INTAKE_TEMP", "AMBIENT_AIR_TEMP", "BAROMETRIC_PRESSURE"],
    "performance": ["RPM", "SPEED", "ENGINE_LOAD", "THROTTLE_POS", "MAF"],
    "economy": ["RPM", "SPEED", "MAF", "ENGINE_LOAD", "FUEL_LEVEL"],
    "all": list(COMMON_PIDS.keys()),
}
