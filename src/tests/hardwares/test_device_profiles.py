"""
Unit tests for device profiles.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

import pytest

from umik_base_app.hardwares.device_profiles import (
    DAYTON_UMM6,
    PROFILES,
    UMIK_1,
    UMIK_2,
    USB_PROFILES,
    CalibrationFormat,
    ConnectionType,
    MicrophoneProfile,
    find_profile_by_name,
    get_profile,
    list_profiles,
    validate_sample_rate,
)


class TestMicrophoneProfile:
    """Tests for MicrophoneProfile dataclass."""

    def test_umik1_single_sample_rate(self):
        """UMIK-1 only supports 48kHz."""
        assert UMIK_1.sample_rates == (48000,)
        assert UMIK_1.default_sample_rate == 48000
        assert UMIK_1.max_sample_rate == 48000
        assert UMIK_1.supports_sample_rate(48000)
        assert not UMIK_1.supports_sample_rate(96000)

    def test_umik2_multiple_sample_rates(self):
        """UMIK-2 supports multiple sample rates."""
        assert UMIK_2.sample_rates == (48000, 96000, 192000)
        assert UMIK_2.default_sample_rate == 48000
        assert UMIK_2.max_sample_rate == 192000
        assert UMIK_2.supports_sample_rate(48000)
        assert UMIK_2.supports_sample_rate(96000)
        assert UMIK_2.supports_sample_rate(192000)
        assert not UMIK_2.supports_sample_rate(44100)

    def test_profile_is_frozen(self):
        """Profiles should be immutable."""
        with pytest.raises(Exception):  # FrozenInstanceError
            UMIK_1.name = "Modified"

    def test_usb_mic_connection_type(self):
        """USB mics should have USB connection type."""
        assert UMIK_1.connection_type == ConnectionType.USB
        assert UMIK_2.connection_type == ConnectionType.USB
        assert DAYTON_UMM6.connection_type == ConnectionType.USB

    def test_calibration_format(self):
        """miniDSP mics use MINIDSP_TXT format."""
        assert UMIK_1.calibration_format == CalibrationFormat.MINIDSP_TXT
        assert UMIK_2.calibration_format == CalibrationFormat.MINIDSP_TXT


class TestProfileRegistry:
    """Tests for profile registry functions."""

    def test_profiles_dict_not_empty(self):
        """Registry should contain profiles."""
        assert len(PROFILES) > 0

    def test_get_profile_by_id(self):
        """Can retrieve profile by model_id."""
        profile = get_profile("minidsp_umik1")
        assert profile is not None
        assert profile.name == "UMIK-1"

    def test_get_profile_not_found(self):
        """Returns None for unknown model_id."""
        assert get_profile("unknown_device") is None

    def test_list_profiles(self):
        """list_profiles returns all profiles."""
        profiles = list_profiles()
        assert len(profiles) == len(PROFILES)
        assert all(isinstance(p, MicrophoneProfile) for p in profiles)

    def test_usb_profiles_subset(self):
        """USB_PROFILES only contains USB devices."""
        for profile in USB_PROFILES.values():
            assert profile.connection_type == ConnectionType.USB


class TestFindProfileByName:
    """Tests for USB device name matching."""

    def test_find_umik1_exact(self):
        """Match UMIK-1 by exact name."""
        profile = find_profile_by_name("UMIK-1")
        assert profile is not None
        assert profile.model_id == "minidsp_umik1"

    def test_find_umik1_case_insensitive(self):
        """Match should be case-insensitive."""
        profile = find_profile_by_name("umik-1")
        assert profile is not None
        assert profile.model_id == "minidsp_umik1"

    def test_find_umik1_substring(self):
        """Match by substring in longer device name."""
        profile = find_profile_by_name("USB Audio Device: miniDSP UMIK-1")
        assert profile is not None
        assert profile.model_id == "minidsp_umik1"

    def test_find_umik2(self):
        """Match UMIK-2."""
        profile = find_profile_by_name("UMIK-2")
        assert profile is not None
        assert profile.model_id == "minidsp_umik2"

    def test_find_dayton(self):
        """Match Dayton Audio UMM-6."""
        profile = find_profile_by_name("Dayton Audio UMM-6")
        assert profile is not None
        assert profile.model_id == "dayton_umm6"

    def test_find_unknown_device(self):
        """Returns None for unknown device."""
        profile = find_profile_by_name("Generic USB Microphone")
        assert profile is None


class TestValidateSampleRate:
    """Tests for sample rate validation."""

    def test_valid_rate_umik1(self):
        """Valid rate for UMIK-1."""
        assert validate_sample_rate(UMIK_1, 48000) is True

    def test_invalid_rate_umik1(self):
        """Invalid rate for UMIK-1."""
        assert validate_sample_rate(UMIK_1, 96000) is False

    def test_valid_rates_umik2(self):
        """All valid rates for UMIK-2."""
        assert validate_sample_rate(UMIK_2, 48000) is True
        assert validate_sample_rate(UMIK_2, 96000) is True
        assert validate_sample_rate(UMIK_2, 192000) is True

    def test_invalid_rate_umik2(self):
        """Invalid rate for UMIK-2."""
        assert validate_sample_rate(UMIK_2, 44100) is False
