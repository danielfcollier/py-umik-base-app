"""
Device profiles for calibrated measurement microphones.

This module defines capabilities and specifications for common calibrated
USB measurement microphones, enabling sample rate validation and
device-specific configuration.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class CalibrationFormat(Enum):
    """Supported calibration file formats."""

    MINIDSP_TXT = "minidsp_txt"  # miniDSP format: "Sens Factor=-X.XdB" header + freq/gain pairs
    REW_TXT = "rew_txt"  # Room EQ Wizard format
    DAYTON_TXT = "dayton_txt"  # Dayton Audio format
    SONARWORKS = "sonarworks"  # Sonarworks XREF format
    GENERIC_CSV = "generic_csv"  # Generic freq,gain CSV


class ConnectionType(Enum):
    """Microphone connection type."""

    USB = "usb"  # Direct USB connection
    ANALOG = "analog"  # Requires external audio interface
    XLR_USB = "xlr_usb"  # XLR mic with USB interface


@dataclass(frozen=True)
class MicrophoneProfile:
    """
    Defines capabilities and specifications for a measurement microphone.

    Attributes:
        name: Human-readable microphone name.
        manufacturer: Manufacturer name.
        model_id: Unique model identifier for matching.
        sample_rates: Supported sample rates in Hz.
        bit_depth: Native bit depth (typically 24 for measurement mics).
        nominal_sensitivity_dbfs: Typical sensitivity at reference SPL.
        reference_dbspl: Reference SPL for sensitivity (usually 94 dBSPL).
        calibration_format: Expected calibration file format.
        connection_type: How the mic connects to the system.
        usb_name_patterns: Patterns to match in USB device name.
        notes: Additional information about the microphone.
    """

    name: str
    manufacturer: str
    model_id: str
    sample_rates: tuple[int, ...]
    bit_depth: int = 24
    nominal_sensitivity_dbfs: float = -18.0
    reference_dbspl: float = 94.0
    calibration_format: CalibrationFormat = CalibrationFormat.MINIDSP_TXT
    connection_type: ConnectionType = ConnectionType.USB
    usb_name_patterns: tuple[str, ...] = field(default_factory=tuple)
    notes: str = ""

    @property
    def default_sample_rate(self) -> int:
        """The default/native sample rate (first in list)."""
        return self.sample_rates[0]

    @property
    def max_sample_rate(self) -> int:
        """Maximum supported sample rate."""
        return max(self.sample_rates)

    def supports_sample_rate(self, rate: int) -> bool:
        """Check if a sample rate is supported."""
        return rate in self.sample_rates


# =============================================================================
# USB Measurement Microphones
# =============================================================================

UMIK_1 = MicrophoneProfile(
    name="UMIK-1",
    manufacturer="miniDSP",
    model_id="minidsp_umik1",
    sample_rates=(48000,),
    bit_depth=24,
    nominal_sensitivity_dbfs=-18.0,
    reference_dbspl=94.0,
    calibration_format=CalibrationFormat.MINIDSP_TXT,
    connection_type=ConnectionType.USB,
    usb_name_patterns=("UMIK-1", "miniDSP UMIK-1"),
    notes="Popular entry-level USB measurement mic. Individual calibration file.",
)

UMIK_2 = MicrophoneProfile(
    name="UMIK-2",
    manufacturer="miniDSP",
    model_id="minidsp_umik2",
    sample_rates=(48000, 96000, 192000),
    bit_depth=24,
    nominal_sensitivity_dbfs=-18.0,
    reference_dbspl=94.0,
    calibration_format=CalibrationFormat.MINIDSP_TXT,
    connection_type=ConnectionType.USB,
    usb_name_patterns=("UMIK-2", "miniDSP UMIK-2"),
    notes="Multi-sample-rate USB mic. May have per-sample-rate calibration files.",
)

DAYTON_UMM6 = MicrophoneProfile(
    name="UMM-6",
    manufacturer="Dayton Audio",
    model_id="dayton_umm6",
    sample_rates=(48000,),
    bit_depth=24,
    nominal_sensitivity_dbfs=-18.0,
    reference_dbspl=94.0,
    calibration_format=CalibrationFormat.DAYTON_TXT,
    connection_type=ConnectionType.USB,
    usb_name_patterns=("UMM-6", "Dayton Audio UMM-6", "Dayton UMM6"),
    notes="Budget-friendly USB measurement mic with individual calibration.",
)

SONARWORKS_XREF20 = MicrophoneProfile(
    name="XREF 20",
    manufacturer="Sonarworks",
    model_id="sonarworks_xref20",
    sample_rates=(48000,),
    bit_depth=24,
    nominal_sensitivity_dbfs=-26.0,  # Different sensitivity
    reference_dbspl=94.0,
    calibration_format=CalibrationFormat.SONARWORKS,
    connection_type=ConnectionType.USB,
    usb_name_patterns=("XREF 20", "Sonarworks"),
    notes="Designed for Sonarworks room correction. Individual calibration.",
)

ISEMCON_EMX7150 = MicrophoneProfile(
    name="EMX-7150",
    manufacturer="iSEMcon",
    model_id="isemcon_emx7150",
    sample_rates=(48000, 96000),
    bit_depth=24,
    nominal_sensitivity_dbfs=-26.0,
    reference_dbspl=94.0,
    calibration_format=CalibrationFormat.GENERIC_CSV,
    connection_type=ConnectionType.USB,
    usb_name_patterns=("EMX-7150", "iSEMcon"),
    notes="Professional USB measurement mic from Cross-Spectrum Labs.",
)

# =============================================================================
# Analog Measurement Microphones (require external interface)
# =============================================================================

BEYERDYNAMIC_MM1 = MicrophoneProfile(
    name="MM 1",
    manufacturer="Beyerdynamic",
    model_id="beyerdynamic_mm1",
    sample_rates=(44100, 48000, 96000, 192000),  # Depends on interface
    bit_depth=24,
    nominal_sensitivity_dbfs=-40.0,  # Lower, requires preamp gain
    reference_dbspl=94.0,
    calibration_format=CalibrationFormat.GENERIC_CSV,
    connection_type=ConnectionType.ANALOG,
    usb_name_patterns=(),  # Analog - no USB pattern
    notes="Professional analog measurement mic. Requires phantom power.",
)

EARTHWORKS_M23 = MicrophoneProfile(
    name="M23",
    manufacturer="Earthworks",
    model_id="earthworks_m23",
    sample_rates=(44100, 48000, 96000, 192000),
    bit_depth=24,
    nominal_sensitivity_dbfs=-36.0,
    reference_dbspl=94.0,
    calibration_format=CalibrationFormat.GENERIC_CSV,
    connection_type=ConnectionType.ANALOG,
    usb_name_patterns=(),
    notes="High-precision analog measurement mic. Flat to 23kHz.",
)

EARTHWORKS_M30 = MicrophoneProfile(
    name="M30",
    manufacturer="Earthworks",
    model_id="earthworks_m30",
    sample_rates=(44100, 48000, 96000, 192000),
    bit_depth=24,
    nominal_sensitivity_dbfs=-36.0,
    reference_dbspl=94.0,
    calibration_format=CalibrationFormat.GENERIC_CSV,
    connection_type=ConnectionType.ANALOG,
    usb_name_patterns=(),
    notes="High-precision analog measurement mic. Flat to 30kHz.",
)

AUDIX_TM1_PLUS = MicrophoneProfile(
    name="TM1 Plus",
    manufacturer="Audix",
    model_id="audix_tm1plus",
    sample_rates=(44100, 48000, 96000),
    bit_depth=24,
    nominal_sensitivity_dbfs=-38.0,
    reference_dbspl=94.0,
    calibration_format=CalibrationFormat.GENERIC_CSV,
    connection_type=ConnectionType.ANALOG,
    usb_name_patterns=(),
    notes="Compact measurement mic with individual calibration certificate.",
)

# =============================================================================
# Profile Registry
# =============================================================================

# All registered profiles indexed by model_id
PROFILES: dict[str, MicrophoneProfile] = {
    profile.model_id: profile
    for profile in [
        UMIK_1,
        UMIK_2,
        DAYTON_UMM6,
        SONARWORKS_XREF20,
        ISEMCON_EMX7150,
        BEYERDYNAMIC_MM1,
        EARTHWORKS_M23,
        EARTHWORKS_M30,
        AUDIX_TM1_PLUS,
    ]
}

# USB profiles only (for auto-detection)
USB_PROFILES: dict[str, MicrophoneProfile] = {
    k: v for k, v in PROFILES.items() if v.connection_type == ConnectionType.USB
}


def find_profile_by_name(device_name: str) -> MicrophoneProfile | None:
    """
    Find a microphone profile by matching USB device name patterns.

    :param device_name: The USB device name reported by the system.
    :return: Matching MicrophoneProfile or None if no match.
    """
    device_name_lower = device_name.lower()
    for profile in USB_PROFILES.values():
        for pattern in profile.usb_name_patterns:
            if pattern.lower() in device_name_lower:
                logger.info(f"Matched device '{device_name}' to profile: {profile.name}")
                return profile
    return None


def get_profile(model_id: str) -> MicrophoneProfile | None:
    """
    Get a microphone profile by its model ID.

    :param model_id: The unique model identifier (e.g., 'minidsp_umik2').
    :return: MicrophoneProfile or None if not found.
    """
    return PROFILES.get(model_id)


def list_profiles() -> list[MicrophoneProfile]:
    """Return all registered microphone profiles."""
    return list(PROFILES.values())


def validate_sample_rate(profile: MicrophoneProfile, sample_rate: int) -> bool:
    """
    Validate that a sample rate is supported by a microphone profile.

    :param profile: The microphone profile to check against.
    :param sample_rate: The desired sample rate in Hz.
    :return: True if supported, False otherwise.
    :raises ValueError: If sample rate is not supported (optional strict mode).
    """
    if profile.supports_sample_rate(sample_rate):
        return True

    logger.warning(
        f"Sample rate {sample_rate}Hz not supported by {profile.name}. Supported rates: {profile.sample_rates}"
    )
    return False
