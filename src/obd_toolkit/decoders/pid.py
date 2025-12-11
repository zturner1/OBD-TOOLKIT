"""PID decoder for interpreting parameter values."""

from typing import Optional, Union, Dict, Any
from enum import Enum


class UnitSystem(str, Enum):
    """Unit system for conversions."""
    METRIC = "metric"
    IMPERIAL = "imperial"


class PIDDecoder:
    """Decodes and converts PID values."""

    def __init__(self, unit_system: UnitSystem = UnitSystem.METRIC):
        """
        Initialize decoder with preferred unit system.

        Args:
            unit_system: Preferred unit system for conversions
        """
        self._unit_system = unit_system

    @property
    def unit_system(self) -> UnitSystem:
        """Get current unit system."""
        return self._unit_system

    @unit_system.setter
    def unit_system(self, value: UnitSystem) -> None:
        """Set unit system."""
        self._unit_system = value

    def convert_speed(self, kph: float) -> tuple[float, str]:
        """
        Convert speed to preferred unit.

        Args:
            kph: Speed in km/h

        Returns:
            Tuple of (value, unit_string)
        """
        if self._unit_system == UnitSystem.IMPERIAL:
            return kph * 0.621371, "mph"
        return kph, "km/h"

    def convert_temperature(self, celsius: float) -> tuple[float, str]:
        """
        Convert temperature to preferred unit.

        Args:
            celsius: Temperature in Celsius

        Returns:
            Tuple of (value, unit_string)
        """
        if self._unit_system == UnitSystem.IMPERIAL:
            return celsius * 9/5 + 32, "F"
        return celsius, "C"

    def convert_distance(self, km: float) -> tuple[float, str]:
        """
        Convert distance to preferred unit.

        Args:
            km: Distance in kilometers

        Returns:
            Tuple of (value, unit_string)
        """
        if self._unit_system == UnitSystem.IMPERIAL:
            return km * 0.621371, "mi"
        return km, "km"

    def convert_pressure(self, kpa: float, target: str = "auto") -> tuple[float, str]:
        """
        Convert pressure to preferred unit.

        Args:
            kpa: Pressure in kPa
            target: Target unit ('psi', 'bar', 'inHg', 'auto')

        Returns:
            Tuple of (value, unit_string)
        """
        if target == "auto":
            target = "psi" if self._unit_system == UnitSystem.IMPERIAL else "kPa"

        conversions = {
            "psi": (kpa * 0.145038, "psi"),
            "bar": (kpa / 100, "bar"),
            "inHg": (kpa * 0.2953, "inHg"),
            "kPa": (kpa, "kPa"),
        }
        return conversions.get(target, (kpa, "kPa"))

    def convert_fuel_rate(self, lph: float) -> tuple[float, str]:
        """
        Convert fuel rate to preferred unit.

        Args:
            lph: Fuel rate in liters per hour

        Returns:
            Tuple of (value, unit_string)
        """
        if self._unit_system == UnitSystem.IMPERIAL:
            return lph * 0.264172, "gal/h"
        return lph, "L/h"

    def interpret_fuel_status(self, status_code: int) -> str:
        """
        Interpret fuel system status code.

        Args:
            status_code: Raw status code from vehicle

        Returns:
            Human-readable status string
        """
        statuses = {
            0: "Unknown",
            1: "Open loop (cold)",
            2: "Closed loop (O2 feedback)",
            4: "Open loop (load/decel)",
            8: "Open loop (system failure)",
            16: "Closed loop (feedback fault)",
        }
        return statuses.get(status_code, f"Unknown ({status_code})")

    def interpret_obd_compliance(self, compliance_code: int) -> str:
        """
        Interpret OBD compliance standard.

        Args:
            compliance_code: Raw compliance code

        Returns:
            Human-readable standard name
        """
        standards = {
            1: "OBD-II (CARB)",
            2: "OBD (EPA)",
            3: "OBD and OBD-II",
            4: "OBD-I",
            5: "Not OBD compliant",
            6: "EOBD (Europe)",
            7: "EOBD and OBD-II",
            8: "EOBD and OBD",
            9: "EOBD, OBD and OBD-II",
            10: "JOBD (Japan)",
            11: "JOBD and OBD-II",
            12: "JOBD and EOBD",
            13: "JOBD, EOBD and OBD-II",
            17: "EMD (Heavy Duty)",
            18: "EMD+",
            19: "HD OBD-C",
            20: "HD OBD",
            21: "WWH OBD",
            23: "HD EOBD-I",
            24: "HD EOBD-I N",
            25: "HD EOBD-II",
            26: "HD EOBD-II N",
            28: "OBDBr-1",
            29: "OBDBr-2",
            30: "KOBD",
            31: "IOBD I",
            32: "IOBD II",
            33: "HD EOBD-IV",
        }
        return standards.get(compliance_code, f"Unknown ({compliance_code})")

    def calculate_fuel_economy(
        self,
        maf: float,
        speed: float,
        fuel_type: str = "gasoline"
    ) -> Optional[Dict[str, Any]]:
        """
        Calculate fuel economy from MAF and speed.

        Args:
            maf: Mass Air Flow in g/s
            speed: Vehicle speed in km/h
            fuel_type: Type of fuel ('gasoline', 'diesel')

        Returns:
            Dictionary with fuel economy values or None if invalid
        """
        if maf <= 0 or speed <= 0:
            return None

        # Air/fuel ratio (stoichiometric)
        afr = 14.7 if fuel_type == "gasoline" else 14.5

        # Fuel density (g/L)
        density = 750 if fuel_type == "gasoline" else 850

        # Fuel consumption in L/h
        fuel_lph = (maf * 3600) / (afr * density)

        # L/100km
        l_per_100km = (fuel_lph / speed) * 100

        # MPG (US)
        mpg_us = 235.215 / l_per_100km if l_per_100km > 0 else 0

        # MPG (UK/Imperial)
        mpg_uk = 282.481 / l_per_100km if l_per_100km > 0 else 0

        return {
            "l_per_100km": round(l_per_100km, 2),
            "mpg_us": round(mpg_us, 1),
            "mpg_uk": round(mpg_uk, 1),
            "fuel_rate_lph": round(fuel_lph, 2),
            "fuel_type": fuel_type,
        }

    def analyze_fuel_trim(self, short_term: float, long_term: float) -> Dict[str, Any]:
        """
        Analyze fuel trim values.

        Args:
            short_term: Short term fuel trim percentage
            long_term: Long term fuel trim percentage

        Returns:
            Dictionary with analysis results
        """
        total_trim = short_term + long_term
        status = "normal"
        issues = []

        # Analyze short term
        if abs(short_term) > 10:
            if short_term > 0:
                issues.append("Short term trim high - possible lean condition")
            else:
                issues.append("Short term trim low - possible rich condition")

        # Analyze long term
        if abs(long_term) > 10:
            if long_term > 0:
                issues.append("Long term trim high - chronic lean condition (check for vacuum leaks)")
            else:
                issues.append("Long term trim low - chronic rich condition (check fuel system)")
            status = "warning"

        # Severe conditions
        if abs(total_trim) > 25:
            status = "critical"
            issues.append("Total fuel trim out of range - significant fuel system issue")

        return {
            "short_term": short_term,
            "long_term": long_term,
            "total": total_trim,
            "status": status,
            "issues": issues,
            "is_lean": total_trim > 5,
            "is_rich": total_trim < -5,
        }

    def analyze_o2_sensor(self, voltage: float, response_time_ms: Optional[float] = None) -> Dict[str, Any]:
        """
        Analyze O2 sensor reading.

        Args:
            voltage: O2 sensor voltage (0-1V typically)
            response_time_ms: Sensor response time if available

        Returns:
            Dictionary with analysis results
        """
        status = "normal"
        issues = []
        mixture = "stoichiometric"

        # Analyze voltage
        if voltage < 0.1:
            mixture = "very lean"
            status = "warning"
            issues.append("Very low O2 voltage - extremely lean condition")
        elif voltage < 0.45:
            mixture = "lean"
        elif voltage > 0.9:
            mixture = "very rich"
            status = "warning"
            issues.append("Very high O2 voltage - extremely rich condition")
        elif voltage > 0.55:
            mixture = "rich"

        # Stuck sensor detection
        if voltage == 0.45 or (voltage > 0.44 and voltage < 0.46):
            issues.append("O2 voltage constant at 0.45V - possible stuck sensor")
            status = "warning"

        # Response time analysis
        if response_time_ms is not None:
            if response_time_ms > 100:
                issues.append(f"Slow O2 sensor response ({response_time_ms}ms) - sensor may be aging")
                status = "warning" if status != "critical" else status

        return {
            "voltage": voltage,
            "mixture": mixture,
            "status": status,
            "issues": issues,
            "response_time_ms": response_time_ms,
        }

    def analyze_coolant_temp(self, temp_celsius: float, ambient_celsius: Optional[float] = None) -> Dict[str, Any]:
        """
        Analyze engine coolant temperature.

        Args:
            temp_celsius: Coolant temperature in Celsius
            ambient_celsius: Ambient air temperature if available

        Returns:
            Dictionary with analysis results
        """
        status = "normal"
        issues = []
        condition = "normal"

        if temp_celsius < 70:
            condition = "cold"
            issues.append("Engine not at operating temperature")
        elif temp_celsius < 85:
            condition = "warming"
        elif temp_celsius <= 105:
            condition = "optimal"
        elif temp_celsius <= 115:
            condition = "warm"
            status = "warning"
            issues.append("Coolant temperature elevated - monitor closely")
        else:
            condition = "overheating"
            status = "critical"
            issues.append("Engine overheating! Stop and check cooling system")

        # Check if thermostat might be stuck
        if ambient_celsius is not None and temp_celsius < ambient_celsius + 20:
            issues.append("Coolant temp near ambient after running - possible stuck thermostat")

        return {
            "temperature_c": temp_celsius,
            "condition": condition,
            "status": status,
            "issues": issues,
            "optimal_range": (85, 105),
        }
