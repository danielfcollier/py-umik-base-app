"""
Tests for AppConfig argument parsing and validation.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

import argparse
from unittest.mock import patch

import pytest

from py_umik.core.config import AppArgs
from py_umik.settings import get_settings

settings = get_settings()


@pytest.fixture
def mock_hardware_selector():
    """Mock the HardwareSelector to prevent hardware calls."""
    with patch("py_umik.core.config.HardwareSelector") as mock:
        # Setup a default dummy device
        hardware_instance = mock.return_value
        hardware_instance.id = 1
        hardware_instance.name = "Dummy Device"
        hardware_instance.native_rate = 48000
        hardware_instance.is_default = True
        yield mock


def test_validate_args_adjusts_buffer(mock_hardware_selector):
    """Test that buffer size is adjusted to meet minimums and LUFS multiples."""
    # Force settings for predictable logic
    settings.AUDIO.MIN_BUFFER_SECONDS = 3.0
    settings.AUDIO.LUFS_WINDOW_SECONDS = 3

    # Request too small buffer (1s)
    args = argparse.Namespace(
        device_id=None,
        buffer_seconds=1.0,
        sample_rate=48000,
        calibration_file=None,
        num_taps=1024,
        default=False,  # <--- FIX: Added missing attribute
    )

    config = AppArgs.validate_args(args)

    # Should be raised to minimum (3.0)
    assert config.buffer_seconds == 3.0


def test_validate_args_adjusts_buffer_rounding(mock_hardware_selector):
    """Test that buffer is rounded up to match LUFS window."""
    settings.AUDIO.MIN_BUFFER_SECONDS = 3.0
    settings.AUDIO.LUFS_WINDOW_SECONDS = 3

    # Request 4s buffer (not divisible by 3)
    args = argparse.Namespace(
        device_id=None,
        buffer_seconds=4.0,
        sample_rate=48000,
        calibration_file=None,
        num_taps=1024,
        default=False,  # <--- FIX: Added missing attribute
    )

    config = AppArgs.validate_args(args)

    # Should be rounded up to 6.0 (next multiple of 3)
    assert config.buffer_seconds == 6.0


@patch("py_umik.core.config.HardwareCalibrator")
def test_validate_args_with_calibration(mock_calibrator_cls, mock_hardware_selector):
    """Test valid configuration with a non-default device and calibration file."""
    # Setup mocks
    mock_calibrator_cls.get_sensitivity_values.return_value = (-18.0, 94.0)

    # Explicitly simulate a non-default device for this test
    mock_hardware_selector.return_value.is_default = False

    args = argparse.Namespace(
        device_id=99,
        buffer_seconds=6.0,
        sample_rate=44100,
        calibration_file="/path/to/cal.txt",
        num_taps=512,
        default=False,  # <--- FIX: Added missing attribute
    )

    config = AppArgs.validate_args(args)

    # Should use the device's native rate (48000 from mock) overriding the requested 44100
    assert config.sample_rate == 48000
    assert config.audio_calibrator is not None
    assert config.sensitivity_dbfs == -18.0
    assert config.num_taps == 512


def test_no_calibration_file_allows_uncalibrated_setup(mock_hardware_selector):
    """
    Test that no error is raised if a non-default device is used without calibration.
    It should simply proceed with calibration disabled.
    """
    # Explicitly simulate a non-default device for this test
    mock_hardware_selector.return_value.is_default = False

    args = argparse.Namespace(
        device_id=99,
        buffer_seconds=6.0,
        sample_rate=48000,
        calibration_file=None,
        num_taps=1024,
        default=False,
    )

    # ACTION: This should now succeed (not raise ValueError)
    config = AppArgs.validate_args(args)

    # ASSERT: Calibration is disabled (None), but the device ID is still respected
    assert config.audio_calibrator is None
    assert config.audio_device.id == mock_hardware_selector.return_value.id
