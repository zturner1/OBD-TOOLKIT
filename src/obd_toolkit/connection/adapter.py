"""OBD2 adapter detection and configuration."""

import sys
from typing import Optional, List
from dataclasses import dataclass
from enum import Enum

import serial.tools.list_ports


class AdapterType(str, Enum):
    """Type of OBD2 adapter."""
    USB_ELM327 = "USB ELM327"
    BLUETOOTH_ELM327 = "Bluetooth ELM327"
    WIFI_ELM327 = "WiFi ELM327"
    UNKNOWN = "Unknown"


@dataclass
class AdapterInfo:
    """Information about a detected OBD2 adapter."""
    port: str
    description: str
    adapter_type: AdapterType
    hwid: str = ""
    manufacturer: str = ""
    vid: Optional[int] = None
    pid: Optional[int] = None

    @property
    def display_name(self) -> str:
        """Human-readable display name."""
        return f"{self.adapter_type.value} on {self.port}"

    def __str__(self) -> str:
        return self.display_name


class AdapterDetector:
    """Detects and identifies OBD2 adapters."""

    # Common USB VID/PID combinations for ELM327 adapters
    KNOWN_ELM327_IDS = [
        (0x0403, 0x6001),  # FTDI FT232R (most common)
        (0x067B, 0x2303),  # Prolific PL2303
        (0x10C4, 0xEA60),  # Silicon Labs CP210x
        (0x1A86, 0x7523),  # CH340
        (0x0403, 0x6015),  # FTDI FT231X
        (0x1A86, 0x5523),  # CH341
        (0x2341, 0x0043),  # Arduino (sometimes used)
    ]

    # Keywords that indicate an ELM327 adapter
    ELM327_KEYWORDS = [
        "elm327", "elm 327", "obd", "obdii", "obd2", "obd-ii",
        "can", "j1850", "iso9141", "kwp2000", "diagnostic"
    ]

    # Bluetooth serial port patterns
    BLUETOOTH_PATTERNS = [
        "bluetooth", "bt", "rfcomm", "bthenum", "bth"
    ]

    @classmethod
    def detect_all(cls) -> List[AdapterInfo]:
        """Detect all potential OBD2 adapters."""
        adapters = []
        ports = serial.tools.list_ports.comports()

        for port in ports:
            adapter = cls._analyze_port(port)
            if adapter:
                adapters.append(adapter)

        return adapters

    @classmethod
    def detect_elm327(cls) -> List[AdapterInfo]:
        """Detect only ELM327-compatible adapters."""
        all_adapters = cls.detect_all()
        return [a for a in all_adapters if "ELM327" in a.adapter_type.value]

    @classmethod
    def find_best_adapter(cls) -> Optional[AdapterInfo]:
        """Find the most likely OBD2 adapter."""
        adapters = cls.detect_all()

        if not adapters:
            return None

        # Prefer USB over Bluetooth
        usb_adapters = [a for a in adapters if a.adapter_type == AdapterType.USB_ELM327]
        if usb_adapters:
            return usb_adapters[0]

        # Then Bluetooth
        bt_adapters = [a for a in adapters if a.adapter_type == AdapterType.BLUETOOTH_ELM327]
        if bt_adapters:
            return bt_adapters[0]

        # Any adapter
        return adapters[0] if adapters else None

    @classmethod
    def _analyze_port(cls, port) -> Optional[AdapterInfo]:
        """Analyze a serial port to determine if it's an OBD2 adapter."""
        port_name = port.device
        description = port.description or ""
        hwid = port.hwid or ""
        manufacturer = port.manufacturer or ""

        # Extract VID/PID if available
        vid = getattr(port, 'vid', None)
        pid = getattr(port, 'pid', None)

        # Combine all info for keyword matching
        all_info = f"{description} {hwid} {manufacturer}".lower()

        # Check if it's a known ELM327 device by VID/PID
        is_known_elm327 = False
        if vid and pid:
            is_known_elm327 = (vid, pid) in cls.KNOWN_ELM327_IDS

        # Check for ELM327 keywords
        has_elm327_keyword = any(kw in all_info for kw in cls.ELM327_KEYWORDS)

        # Check if it's Bluetooth
        is_bluetooth = any(pattern in all_info for pattern in cls.BLUETOOTH_PATTERNS)

        # Determine adapter type
        adapter_type = AdapterType.UNKNOWN

        if is_known_elm327 or has_elm327_keyword:
            if is_bluetooth:
                adapter_type = AdapterType.BLUETOOTH_ELM327
            else:
                adapter_type = AdapterType.USB_ELM327
        elif is_bluetooth:
            # Bluetooth port but not confirmed ELM327
            adapter_type = AdapterType.BLUETOOTH_ELM327
        elif cls._is_likely_serial_adapter(port):
            # Generic serial that might be ELM327
            adapter_type = AdapterType.USB_ELM327

        # Only return if it's potentially an OBD adapter
        if adapter_type != AdapterType.UNKNOWN:
            return AdapterInfo(
                port=port_name,
                description=description,
                adapter_type=adapter_type,
                hwid=hwid,
                manufacturer=manufacturer,
                vid=vid,
                pid=pid,
            )

        return None

    @classmethod
    def _is_likely_serial_adapter(cls, port) -> bool:
        """Check if port is likely a USB-to-serial adapter."""
        description = (port.description or "").lower()
        manufacturer = (port.manufacturer or "").lower()

        serial_keywords = [
            "usb", "serial", "uart", "ftdi", "prolific", "ch340",
            "cp210", "silicon labs", "converter"
        ]

        return any(kw in description or kw in manufacturer for kw in serial_keywords)

    @classmethod
    def get_port_by_name(cls, port_name: str) -> Optional[AdapterInfo]:
        """Get adapter info for a specific port name."""
        ports = serial.tools.list_ports.comports()

        for port in ports:
            if port.device == port_name:
                return cls._analyze_port(port) or AdapterInfo(
                    port=port_name,
                    description=port.description or "Unknown",
                    adapter_type=AdapterType.UNKNOWN,
                )

        return None

    @classmethod
    def list_all_ports(cls) -> List[dict]:
        """List all serial ports with detailed info (for debugging)."""
        ports = serial.tools.list_ports.comports()
        result = []

        for port in ports:
            result.append({
                "device": port.device,
                "description": port.description,
                "hwid": port.hwid,
                "manufacturer": port.manufacturer,
                "product": getattr(port, 'product', None),
                "vid": getattr(port, 'vid', None),
                "pid": getattr(port, 'pid', None),
                "serial_number": getattr(port, 'serial_number', None),
            })

        return result
