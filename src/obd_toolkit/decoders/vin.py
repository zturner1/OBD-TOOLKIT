"""VIN decoder for vehicle identification."""

import logging
from typing import Optional, Dict, Any

import httpx

from ..models.vehicle import VehicleInfo

logger = logging.getLogger(__name__)


class VINDecoder:
    """Decodes Vehicle Identification Numbers."""

    NHTSA_API_URL = "https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVin/{vin}?format=json"

    def __init__(self, use_cache: bool = True):
        """
        Initialize VIN decoder.

        Args:
            use_cache: Whether to cache decoded VINs
        """
        self._cache: Dict[str, VehicleInfo] = {}
        self._use_cache = use_cache

    def decode(self, vin: str, use_online: bool = False) -> VehicleInfo:
        """
        Decode a VIN into vehicle information.

        Args:
            vin: 17-character VIN string
            use_online: Use NHTSA API for detailed decoding

        Returns:
            VehicleInfo with decoded information
        """
        vin = vin.upper().strip()

        # Check cache
        cache_key = f"{vin}_{use_online}"
        if self._use_cache and cache_key in self._cache:
            return self._cache[cache_key]

        # Basic offline decoding
        info = VehicleInfo.from_vin(vin)

        # Online decoding if requested and VIN is valid
        if use_online and info.is_valid:
            try:
                online_info = self._decode_nhtsa(vin)
                if online_info:
                    # Merge online data with offline data
                    info = self._merge_info(info, online_info)
            except Exception as e:
                logger.warning(f"Online VIN decode failed: {e}")

        # Cache result
        if self._use_cache:
            self._cache[cache_key] = info

        return info

    def _decode_nhtsa(self, vin: str) -> Optional[Dict[str, Any]]:
        """
        Decode VIN using NHTSA API.

        Args:
            vin: VIN string

        Returns:
            Dictionary with decoded info or None
        """
        url = self.NHTSA_API_URL.format(vin=vin)

        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(url)
                response.raise_for_status()

                data = response.json()
                results = data.get("Results", [])

                # Parse results into dictionary
                decoded = {}
                for item in results:
                    var = item.get("Variable", "")
                    val = item.get("Value")
                    if val and val.strip():
                        decoded[var] = val.strip()

                return decoded

        except httpx.TimeoutException:
            logger.warning("NHTSA API timeout")
        except httpx.HTTPError as e:
            logger.warning(f"NHTSA API error: {e}")
        except Exception as e:
            logger.error(f"NHTSA decode error: {e}")

        return None

    def _merge_info(self, offline: VehicleInfo, online: Dict[str, Any]) -> VehicleInfo:
        """
        Merge online NHTSA data with offline decoded info.

        Args:
            offline: Offline decoded VehicleInfo
            online: Dictionary from NHTSA API

        Returns:
            Merged VehicleInfo
        """
        # Map NHTSA fields to VehicleInfo fields
        field_mapping = {
            "Make": "make",
            "Manufacturer Name": "manufacturer",
            "Model": "model",
            "Model Year": "model_year",
            "Body Class": "body_class",
            "Engine Model": "engine_type",
            "Fuel Type - Primary": "fuel_type",
            "Drive Type": "drive_type",
            "Transmission Style": "transmission",
            "Doors": "doors",
            "Plant Country": "country",
        }

        # Create update dict
        updates = {}
        for nhtsa_field, info_field in field_mapping.items():
            if nhtsa_field in online:
                value = online[nhtsa_field]

                # Handle special conversions
                if info_field == "model_year":
                    try:
                        value = int(value)
                    except (ValueError, TypeError):
                        continue
                elif info_field == "doors":
                    try:
                        value = int(value)
                    except (ValueError, TypeError):
                        continue

                updates[info_field] = value

        # Create new VehicleInfo with updates
        info_dict = offline.model_dump()
        info_dict.update(updates)

        return VehicleInfo(**info_dict)

    def validate_vin(self, vin: str) -> Dict[str, Any]:
        """
        Validate a VIN and return validation details.

        Args:
            vin: VIN string to validate

        Returns:
            Dictionary with validation results
        """
        vin = vin.upper().strip()
        errors = []
        warnings = []

        # Length check
        if len(vin) != 17:
            errors.append(f"VIN must be 17 characters (got {len(vin)})")

        # Invalid character check
        invalid_chars = set(vin) & {"I", "O", "Q"}
        if invalid_chars:
            errors.append(f"VIN contains invalid characters: {invalid_chars}")

        # Alphanumeric check
        if not vin.isalnum():
            errors.append("VIN must contain only letters and numbers")

        # Check digit validation (position 9)
        if len(vin) == 17:
            if not self._validate_check_digit(vin):
                warnings.append("Check digit validation failed - VIN may be incorrect")

        # Year character validation (position 10)
        if len(vin) >= 10:
            year_char = vin[9]
            valid_years = "ABCDEFGHJKLMNPRSTUVWXY123456789"
            if year_char not in valid_years:
                warnings.append(f"Invalid model year character: {year_char}")

        return {
            "vin": vin,
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "length": len(vin),
        }

    def _validate_check_digit(self, vin: str) -> bool:
        """
        Validate VIN check digit (North American VINs).

        Args:
            vin: 17-character VIN

        Returns:
            True if check digit is valid
        """
        if len(vin) != 17:
            return False

        # Transliteration values
        trans = {
            "A": 1, "B": 2, "C": 3, "D": 4, "E": 5, "F": 6, "G": 7, "H": 8,
            "J": 1, "K": 2, "L": 3, "M": 4, "N": 5, "P": 7, "R": 9,
            "S": 2, "T": 3, "U": 4, "V": 5, "W": 6, "X": 7, "Y": 8, "Z": 9,
        }

        # Position weights
        weights = [8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2]

        total = 0
        for i, char in enumerate(vin):
            if char.isdigit():
                value = int(char)
            else:
                value = trans.get(char, 0)
            total += value * weights[i]

        remainder = total % 11
        check_char = vin[8]

        if remainder == 10:
            return check_char == "X"
        else:
            return check_char == str(remainder)

    def get_manufacturer_info(self, wmi: str) -> Dict[str, str]:
        """
        Get manufacturer info from WMI (first 3 characters).

        Args:
            wmi: World Manufacturer Identifier

        Returns:
            Dictionary with manufacturer info
        """
        # This uses the same logic as VehicleInfo._decode_wmi
        info = VehicleInfo.from_vin(wmi + "0" * 14)  # Pad to 17 chars
        return {
            "wmi": wmi,
            "manufacturer": info.manufacturer,
            "country": info.country,
            "region": info.region,
        }

    def clear_cache(self) -> None:
        """Clear the VIN decode cache."""
        self._cache.clear()
