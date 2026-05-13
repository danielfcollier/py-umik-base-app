"""
Device capabilities discovery and validation.

This module provides runtime discovery of audio device capabilities
and integration with device profiles for measurement microphones.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import sounddevice as sd

from .device_profiles import MicrophoneProfile, find_profile_by_name

logger = logging.getLogger(__name__)

# Common sample rates to test for support
COMMON_SAMPLE_RATES = (44100, 48000, 88200, 96000, 176400, 192000)


@dataclass
class DeviceCapabilities:
    """
    Runtime capabilities discovered for an audio device.

    Attributes:
        device_id: The sounddevice device index.
        device_name: The device name as reported by the system.
        supported_sample_rates: Sample rates confirmed to work.
        default_sample_rate: The device's default/native sample rate.
        max_input_channels: Number of input channels available.
        profile: Matched MicrophoneProfile if recognized, else None.
    """

    device_id: int
    device_name: str
    supported_sample_rates: tuple[int, ...]
    default_sample_rate: int
    max_input_channels: int
    profile: MicrophoneProfile | None = None

    @property
    def is_known_device(self) -> bool:
        """True if device matches a known microphone profile."""
        return self.profile is not None

    @property
    def max_sample_rate(self) -> int:
        """Maximum supported sample rate."""
        return max(self.supported_sample_rates) if self.supported_sample_rates else 0

    def supports_rate(self, rate: int) -> bool:
        """Check if a specific sample rate is supported."""
        return rate in self.supported_sample_rates


def query_supported_sample_rates(
    device_id: int,
    channels: int = 1,
    rates_to_test: tuple[int, ...] = COMMON_SAMPLE_RATES,
) -> list[int]:
    """
    Query which sample rates a device actually supports.

    Uses sounddevice to test each rate. This is more reliable than
    trusting device-reported capabilities.

    :param device_id: The sounddevice device index.
    :param channels: Number of channels to test (default 1 for mono mic).
    :param rates_to_test: Sample rates to probe.
    :return: List of supported sample rates.
    """
    supported = []

    for rate in rates_to_test:
        try:
            sd.check_input_settings(
                device=device_id,
                channels=channels,
                samplerate=rate,
            )
            supported.append(rate)
        except sd.PortAudioError:
            # Rate not supported
            pass
        except Exception as e:
            logger.debug(f"Error testing rate {rate} on device {device_id}: {e}")

    return supported


def discover_capabilities(device_id: int) -> DeviceCapabilities:
    """
    Discover full capabilities for an audio device.

    Queries the device for supported sample rates and attempts to match
    it against known microphone profiles.

    :param device_id: The sounddevice device index.
    :return: DeviceCapabilities with discovered information.
    :raises ValueError: If device_id is invalid.
    """
    try:
        device_info = sd.query_devices(device_id)
    except Exception as e:
        raise ValueError(f"Cannot query device {device_id}: {e}") from e

    device_name = device_info["name"]
    default_rate = int(device_info["default_samplerate"])
    max_channels = device_info["max_input_channels"]

    if max_channels == 0:
        raise ValueError(f"Device {device_id} ({device_name}) has no input channels")

    # Discover supported sample rates
    supported_rates = query_supported_sample_rates(device_id)

    # Ensure default rate is in the list
    if default_rate not in supported_rates:
        supported_rates.append(default_rate)
        supported_rates.sort()

    # Try to match against known profiles
    profile = find_profile_by_name(device_name)

    if profile:
        logger.info(f"Device '{device_name}' matched profile: {profile.manufacturer} {profile.name}")
        # Use profile rates if available (more authoritative)
        # But verify against discovered rates
        profile_rates = set(profile.sample_rates)
        discovered_rates = set(supported_rates)
        if not profile_rates.issubset(discovered_rates):
            missing = profile_rates - discovered_rates
            logger.warning(f"Profile claims rates {missing} but device doesn't support them")
    else:
        logger.info(f"Device '{device_name}' not in known profiles. Using discovered rates.")

    return DeviceCapabilities(
        device_id=device_id,
        device_name=device_name,
        supported_sample_rates=tuple(sorted(supported_rates)),
        default_sample_rate=default_rate,
        max_input_channels=max_channels,
        profile=profile,
    )


def select_best_sample_rate(
    capabilities: DeviceCapabilities,
    preferred_rate: int | None = None,
) -> int:
    """
    Select the best sample rate for a device.

    Priority:
    1. Preferred rate if supported
    2. Profile default rate if device has a profile
    3. Device default rate
    4. Highest supported rate

    :param capabilities: Device capabilities to consider.
    :param preferred_rate: User's preferred rate (optional).
    :return: Selected sample rate.
    """
    # Try preferred rate first
    if preferred_rate and capabilities.supports_rate(preferred_rate):
        return preferred_rate

    if preferred_rate:
        logger.warning(
            f"Preferred rate {preferred_rate}Hz not supported. Available: {capabilities.supported_sample_rates}"
        )

    # Use profile default if available
    if capabilities.profile:
        profile_default = capabilities.profile.default_sample_rate
        if capabilities.supports_rate(profile_default):
            return profile_default

    # Fall back to device default
    return capabilities.default_sample_rate


def show_device_capabilities(capabilities: DeviceCapabilities) -> None:
    """
    Log device capabilities in a readable format.

    :param capabilities: The capabilities to display.
    """
    profile_info = ""
    if capabilities.profile:
        p = capabilities.profile
        profile_info = f" [{p.manufacturer} {p.name}]"

    logger.info(f"Device: {capabilities.device_name}{profile_info}")
    logger.info(f"  ID: {capabilities.device_id}")
    logger.info(f"  Channels: {capabilities.max_input_channels}")
    logger.info(f"  Default rate: {capabilities.default_sample_rate}Hz")
    logger.info(f"  Supported rates: {', '.join(str(r) for r in capabilities.supported_sample_rates)}Hz")

    if capabilities.profile:
        logger.info(f"  Nominal sensitivity: {capabilities.profile.nominal_sensitivity_dbfs} dBFS")
        logger.info(f"  Reference SPL: {capabilities.profile.reference_dbspl} dBSPL")
