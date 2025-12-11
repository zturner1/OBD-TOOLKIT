"""VIN (Vehicle Identification Number) collector."""

from typing import Optional
import logging

import obd

from .base import BaseCollector
from ..models.vehicle import VehicleInfo
from ..decoders.vin import VINDecoder

logger = logging.getLogger(__name__)


class VINCollector(BaseCollector):
    """Collects and decodes Vehicle Identification Number."""

    def __init__(self, connection_manager, decoder: Optional[VINDecoder] = None):
        super().__init__(connection_manager)
        self._decoder = decoder or VINDecoder()
        self._cached_vin: Optional[str] = None
        self._cached_info: Optional[VehicleInfo] = None

    def collect(self) -> Optional[VehicleInfo]:
        """Collect and decode VIN from vehicle."""
        vin = self.read_vin()
        if vin:
            return self._decoder.decode(vin)
        return None

    def is_supported(self) -> bool:
        """Check if VIN reading is supported."""
        if not self.connection:
            return False
        return obd.commands.VIN in self.connection.supported_commands

    def read_vin(self, use_cache: bool = True) -> Optional[str]:
        """
        Read VIN from vehicle.

        Args:
            use_cache: Return cached VIN if available

        Returns:
            17-character VIN string or None
        """
        if use_cache and self._cached_vin:
            return self._cached_vin

        self._ensure_connected()

        try:
            response = self.connection.query(obd.commands.VIN)

            if response.is_null():
                logger.warning("No VIN response from vehicle")
                return None

            vin = str(response.value).strip()

            # Validate VIN length
            if len(vin) != 17:
                logger.warning(f"Invalid VIN length: {len(vin)} (expected 17)")
                # Try to extract valid VIN
                vin = self._extract_vin(vin)

            if vin and len(vin) == 17:
                self._cached_vin = vin
                return vin

            return None

        except Exception as e:
            logger.error(f"Error reading VIN: {e}")
            return None

    def get_vehicle_info(self, use_online: bool = False) -> Optional[VehicleInfo]:
        """
        Get full vehicle information.

        Args:
            use_online: Use NHTSA API for additional details

        Returns:
            VehicleInfo with decoded information
        """
        if self._cached_info and not use_online:
            return self._cached_info

        vin = self.read_vin()
        if not vin:
            return None

        info = self._decoder.decode(vin, use_online=use_online)
        self._cached_info = info
        return info

    def clear_cache(self) -> None:
        """Clear cached VIN and vehicle info."""
        self._cached_vin = None
        self._cached_info = None

    @staticmethod
    def _extract_vin(raw: str) -> Optional[str]:
        """Try to extract valid VIN from raw response."""
        # Remove common prefixes/suffixes and whitespace
        cleaned = raw.strip().upper()

        # Remove any non-alphanumeric characters
        cleaned = ''.join(c for c in cleaned if c.isalnum())

        # VINs cannot contain I, O, or Q
        cleaned = cleaned.replace('I', '1').replace('O', '0').replace('Q', '0')

        if len(cleaned) == 17:
            return cleaned

        # Try to find 17-character sequence
        if len(cleaned) > 17:
            # Look for likely VIN start patterns
            for i in range(len(cleaned) - 16):
                potential = cleaned[i:i+17]
                # Check if it starts with valid WMI region code
                if potential[0] in '123456789ABCDEFGHJKLMNPRSTUVWXYZ':
                    return potential

        return None

    def read_calibration_id(self) -> Optional[str]:
        """Read ECU calibration ID (if supported)."""
        self._ensure_connected()

        try:
            if hasattr(obd.commands, 'CALIBRATION_ID'):
                response = self.connection.query(obd.commands.CALIBRATION_ID)
                if not response.is_null():
                    return str(response.value)
        except Exception as e:
            logger.debug(f"Calibration ID not available: {e}")

        return None

    def read_ecu_name(self) -> Optional[str]:
        """Read ECU name (if supported)."""
        self._ensure_connected()

        try:
            if hasattr(obd.commands, 'ECU_NAME'):
                response = self.connection.query(obd.commands.ECU_NAME)
                if not response.is_null():
                    return str(response.value)
        except Exception as e:
            logger.debug(f"ECU name not available: {e}")

        return None
