"""DTC (Diagnostic Trouble Code) collector."""

from typing import List, Optional
import logging

import obd
from obd import OBDCommand

from .base import BaseCollector
from ..models.dtc import DTCInfo, DTCReadResult, DTCType, DTCSeverity
from ..decoders.dtc import DTCDecoder

logger = logging.getLogger(__name__)


class DTCCollector(BaseCollector):
    """Collects Diagnostic Trouble Codes from vehicle."""

    def __init__(self, connection_manager, decoder: Optional[DTCDecoder] = None):
        super().__init__(connection_manager)
        self._decoder = decoder or DTCDecoder()

    def collect(self) -> DTCReadResult:
        """Collect all DTCs from the vehicle."""
        self._ensure_connected()

        result = DTCReadResult(
            stored_codes=self.read_stored(),
            pending_codes=self.read_pending(),
            permanent_codes=self.read_permanent(),
        )

        # Get MIL status
        result.mil_status = self._get_mil_status()

        return result

    def is_supported(self) -> bool:
        """Check if DTC reading is supported."""
        if not self.connection:
            return False
        # Mode 03 (GET_DTC) is standard and should be supported
        return obd.commands.GET_DTC in self.connection.supported_commands

    def read_stored(self) -> List[DTCInfo]:
        """
        Read stored DTCs (Mode 03).

        These are confirmed fault codes that have triggered the MIL.
        """
        self._ensure_connected()

        try:
            response = self.connection.query(obd.commands.GET_DTC)

            if response.is_null():
                logger.debug("No stored DTCs returned")
                return []

            return self._process_dtc_response(response.value, DTCType.STORED)

        except Exception as e:
            logger.error(f"Error reading stored DTCs: {e}")
            return []

    def read_pending(self) -> List[DTCInfo]:
        """
        Read pending DTCs (Mode 07).

        These are fault codes detected but not yet confirmed.
        """
        self._ensure_connected()

        # Mode 07 command for pending DTCs
        try:
            # Try to use GET_FREEZE_DTC or build custom command
            if hasattr(obd.commands, 'GET_FREEZE_DTC'):
                response = self.connection.query(obd.commands.GET_FREEZE_DTC)
            else:
                # Build Mode 07 command manually
                cmd = OBDCommand(
                    "PENDING_DTC",
                    "Pending DTCs",
                    b"07",
                    0,
                    lambda msgs: self._parse_dtc_messages(msgs),
                    fast=True
                )
                response = self.connection.query(cmd)

            if response.is_null():
                return []

            return self._process_dtc_response(response.value, DTCType.PENDING)

        except Exception as e:
            logger.debug(f"Pending DTCs not available: {e}")
            return []

    def read_permanent(self) -> List[DTCInfo]:
        """
        Read permanent DTCs (Mode 0A).

        These are codes that cannot be cleared without repair.
        """
        self._ensure_connected()

        try:
            # Mode 0A command for permanent DTCs
            cmd = OBDCommand(
                "PERMANENT_DTC",
                "Permanent DTCs",
                b"0A",
                0,
                lambda msgs: self._parse_dtc_messages(msgs),
                fast=True
            )
            response = self.connection.query(cmd)

            if response.is_null():
                return []

            return self._process_dtc_response(response.value, DTCType.PERMANENT)

        except Exception as e:
            logger.debug(f"Permanent DTCs not available: {e}")
            return []

    def clear_dtcs(self, force: bool = False) -> bool:
        """
        Clear all DTCs (Mode 04).

        Args:
            force: Skip confirmation prompt (use with caution)

        Returns:
            True if successful, False otherwise
        """
        self._ensure_connected()

        if not force:
            logger.warning("Clearing DTCs without force flag - should confirm with user")

        try:
            response = self.connection.query(obd.commands.CLEAR_DTC)

            if response.is_null():
                logger.warning("No response from clear DTC command")
                return False

            logger.info("DTCs cleared successfully")
            return True

        except Exception as e:
            logger.error(f"Error clearing DTCs: {e}")
            return False

    def _get_mil_status(self) -> bool:
        """Get Malfunction Indicator Lamp (MIL) status."""
        try:
            response = self.connection.query(obd.commands.STATUS)

            if response.is_null():
                return False

            # The STATUS response includes MIL status
            status = response.value
            if hasattr(status, 'MIL'):
                return status.MIL

            return False

        except Exception as e:
            logger.debug(f"Could not get MIL status: {e}")
            return False

    def _process_dtc_response(self, dtc_list, dtc_type: DTCType) -> List[DTCInfo]:
        """Process DTC response into DTCInfo objects."""
        results = []

        if not dtc_list:
            return results

        for dtc in dtc_list:
            # DTC can be a tuple of (code, description) or just code
            if isinstance(dtc, tuple):
                code = dtc[0]
                # Use provided description if available
                base_description = dtc[1] if len(dtc) > 1 else None
            else:
                code = str(dtc)
                base_description = None

            # Decode using our decoder
            decoded = self._decoder.decode(code)

            if decoded:
                decoded.dtc_type = dtc_type
                if base_description and decoded.description == "Unknown code":
                    decoded.description = base_description
                results.append(decoded)
            else:
                # Create basic DTCInfo if decoder fails
                results.append(DTCInfo.from_code(code, base_description or "Unknown", dtc_type))

        return results

    def _parse_dtc_messages(self, messages) -> List[tuple]:
        """Parse raw OBD messages into DTC tuples."""
        dtcs = []

        for msg in messages:
            data = msg.data

            # Each DTC is 2 bytes
            for i in range(0, len(data) - 1, 2):
                byte1 = data[i]
                byte2 = data[i + 1]

                # Skip empty codes (0x0000)
                if byte1 == 0 and byte2 == 0:
                    continue

                code = self._bytes_to_dtc(byte1, byte2)
                if code:
                    dtcs.append((code, ""))

        return dtcs

    @staticmethod
    def _bytes_to_dtc(byte1: int, byte2: int) -> Optional[str]:
        """Convert two bytes to DTC code string."""
        # First two bits of byte1 determine the category
        category_bits = (byte1 >> 6) & 0x03
        categories = {0: 'P', 1: 'C', 2: 'B', 3: 'U'}
        category = categories.get(category_bits, 'P')

        # Remaining bits form the code number
        code_num = ((byte1 & 0x3F) << 8) | byte2

        # Format: Category + 4 hex digits
        return f"{category}{code_num:04X}"
