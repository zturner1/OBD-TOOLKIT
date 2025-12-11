"""Data models for vehicle information."""

from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime


class VehicleInfo(BaseModel):
    """Decoded vehicle information from VIN."""

    vin: str = Field(..., description="17-character Vehicle Identification Number")

    # WMI (World Manufacturer Identifier) - Positions 1-3
    manufacturer: str = Field(default="Unknown", description="Vehicle manufacturer")
    country: str = Field(default="Unknown", description="Country of origin")
    region: str = Field(default="Unknown", description="Manufacturing region")

    # VDS (Vehicle Descriptor Section) - Positions 4-9
    model_year: Optional[int] = Field(default=None, description="Model year")
    assembly_plant: str = Field(default="Unknown", description="Assembly plant code")

    # Additional decoded info
    make: str = Field(default="Unknown", description="Vehicle make")
    model: str = Field(default="Unknown", description="Vehicle model")
    body_class: str = Field(default="Unknown", description="Body type/class")
    engine_type: str = Field(default="Unknown", description="Engine type")
    fuel_type: str = Field(default="Unknown", description="Fuel type")

    # NHTSA API additional info
    drive_type: str = Field(default="Unknown", description="Drive type (FWD, RWD, AWD)")
    transmission: str = Field(default="Unknown", description="Transmission type")
    doors: Optional[int] = Field(default=None, description="Number of doors")

    # Validation
    is_valid: bool = Field(default=True, description="Whether VIN is valid")
    validation_errors: List[str] = Field(default_factory=list, description="Validation errors if any")

    timestamp: datetime = Field(default_factory=datetime.now, description="When VIN was decoded")

    @classmethod
    def from_vin(cls, vin: str) -> "VehicleInfo":
        """Create basic VehicleInfo from VIN with offline decoding."""
        vin = vin.upper().strip()
        errors = cls._validate_vin(vin)

        info = cls(
            vin=vin,
            is_valid=len(errors) == 0,
            validation_errors=errors,
        )

        if info.is_valid:
            info._decode_offline()

        return info

    @staticmethod
    def _validate_vin(vin: str) -> List[str]:
        """Validate VIN format."""
        errors = []

        if len(vin) != 17:
            errors.append(f"VIN must be 17 characters (got {len(vin)})")

        # VINs cannot contain I, O, or Q
        invalid_chars = set(vin) & {"I", "O", "Q"}
        if invalid_chars:
            errors.append(f"VIN contains invalid characters: {invalid_chars}")

        # VINs must be alphanumeric
        if not vin.isalnum():
            errors.append("VIN must contain only letters and numbers")

        return errors

    def _decode_offline(self) -> None:
        """Decode VIN using offline data."""
        if len(self.vin) != 17:
            return

        # Decode WMI (first 3 characters)
        wmi = self.vin[:3]
        self._decode_wmi(wmi)

        # Decode model year (position 10)
        year_char = self.vin[9]
        self.model_year = self._decode_year(year_char)

        # Decode assembly plant (position 11)
        self.assembly_plant = self.vin[10]

    def _decode_wmi(self, wmi: str) -> None:
        """Decode World Manufacturer Identifier."""
        # First character indicates region/country
        region_codes = {
            "1": ("North America", "United States"),
            "2": ("North America", "Canada"),
            "3": ("North America", "Mexico"),
            "4": ("North America", "United States"),
            "5": ("North America", "United States"),
            "J": ("Asia", "Japan"),
            "K": ("Asia", "South Korea"),
            "L": ("Asia", "China"),
            "S": ("Europe", "United Kingdom"),
            "V": ("Europe", "France/Spain"),
            "W": ("Europe", "Germany"),
            "Y": ("Europe", "Sweden/Finland"),
            "Z": ("Europe", "Italy"),
        }

        first_char = wmi[0]
        if first_char in region_codes:
            self.region, self.country = region_codes[first_char]

        # Common WMI codes for manufacturers
        wmi_manufacturers = {
            "1G1": "Chevrolet",
            "1G2": "Pontiac",
            "1GC": "Chevrolet Truck",
            "1GM": "Pontiac",
            "1G6": "Cadillac",
            "1FA": "Ford",
            "1FB": "Ford",
            "1FC": "Ford",
            "1FD": "Ford",
            "1FM": "Ford",
            "1FT": "Ford Truck",
            "1FU": "Freightliner",
            "1C3": "Chrysler",
            "1C4": "Chrysler",
            "1C6": "Chrysler",
            "1D7": "Dodge",
            "1GY": "Cadillac",
            "1HG": "Honda",
            "1J4": "Jeep",
            "1J8": "Jeep",
            "1LN": "Lincoln",
            "1ME": "Mercury",
            "1N4": "Nissan",
            "1N6": "Nissan Truck",
            "1NX": "Toyota (NUMMI)",
            "1VW": "Volkswagen",
            "1YV": "Mazda",
            "1ZV": "Ford (Mazda)",
            "2C3": "Chrysler Canada",
            "2D3": "Dodge Canada",
            "2FA": "Ford Canada",
            "2G1": "Chevrolet Canada",
            "2HG": "Honda Canada",
            "2HK": "Honda Canada",
            "2HM": "Hyundai Canada",
            "2T1": "Toyota Canada",
            "3FA": "Ford Mexico",
            "3G1": "Chevrolet Mexico",
            "3GN": "GMC Mexico",
            "3VW": "Volkswagen Mexico",
            "JA3": "Mitsubishi",
            "JA4": "Mitsubishi",
            "JF1": "Subaru",
            "JF2": "Subaru",
            "JH4": "Acura",
            "JHM": "Honda",
            "JN1": "Nissan",
            "JN8": "Nissan",
            "JT2": "Toyota",
            "JT3": "Toyota",
            "JT4": "Toyota",
            "JTE": "Toyota",
            "JTH": "Lexus",
            "JTD": "Toyota",
            "JTK": "Toyota",
            "JTN": "Toyota",
            "KM8": "Hyundai",
            "KMH": "Hyundai",
            "KNA": "Kia",
            "KNC": "Kia",
            "KND": "Kia",
            "5J6": "Honda",
            "5FN": "Honda",
            "5NP": "Hyundai",
            "5TD": "Toyota",
            "5TF": "Toyota",
            "5YJ": "Tesla",
            "SAJ": "Jaguar",
            "SAL": "Land Rover",
            "SCC": "Lotus",
            "SCF": "Aston Martin",
            "VF1": "Renault",
            "VF3": "Peugeot",
            "VF7": "Citroen",
            "WAU": "Audi",
            "WBA": "BMW",
            "WBS": "BMW M",
            "WDB": "Mercedes-Benz",
            "WDC": "Mercedes-Benz",
            "WDD": "Mercedes-Benz",
            "WF0": "Ford Germany",
            "WP0": "Porsche",
            "WP1": "Porsche",
            "WUA": "Audi",
            "WVG": "Volkswagen",
            "WVW": "Volkswagen",
            "YV1": "Volvo",
            "YV4": "Volvo",
            "ZAM": "Maserati",
            "ZAR": "Alfa Romeo",
            "ZFA": "Fiat",
            "ZFF": "Ferrari",
        }

        if wmi in wmi_manufacturers:
            self.manufacturer = wmi_manufacturers[wmi]
            self.make = wmi_manufacturers[wmi]

    @staticmethod
    def _decode_year(char: str) -> Optional[int]:
        """Decode model year from position 10."""
        # Year codes cycle every 30 years
        year_codes = {
            "A": 2010, "B": 2011, "C": 2012, "D": 2013, "E": 2014,
            "F": 2015, "G": 2016, "H": 2017, "J": 2018, "K": 2019,
            "L": 2020, "M": 2021, "N": 2022, "P": 2023, "R": 2024,
            "S": 2025, "T": 2026, "V": 2027, "W": 2028, "X": 2029,
            "Y": 2030,
            "1": 2001, "2": 2002, "3": 2003, "4": 2004, "5": 2005,
            "6": 2006, "7": 2007, "8": 2008, "9": 2009,
        }
        return year_codes.get(char)

    @property
    def wmi(self) -> str:
        """Get World Manufacturer Identifier (positions 1-3)."""
        return self.vin[:3] if len(self.vin) >= 3 else ""

    @property
    def vds(self) -> str:
        """Get Vehicle Descriptor Section (positions 4-9)."""
        return self.vin[3:9] if len(self.vin) >= 9 else ""

    @property
    def vis(self) -> str:
        """Get Vehicle Identifier Section (positions 10-17)."""
        return self.vin[9:] if len(self.vin) == 17 else ""

    @property
    def serial_number(self) -> str:
        """Get serial number (positions 12-17)."""
        return self.vin[11:] if len(self.vin) == 17 else ""

    def __str__(self) -> str:
        parts = [self.vin]
        if self.manufacturer != "Unknown":
            parts.append(f"{self.manufacturer}")
        if self.model_year:
            parts.append(f"{self.model_year}")
        return " - ".join(parts)
