"""
Tests for AppConfig argument parsing and validation.
"""

import argparse
from unittest.mock import patch

import pytest

from src.py_umik.core.config import AppArgs
from src.py_umik.settings import get_settings

settings = get_settings()


@pytest.fixture
def mock_hardware_selector():
    """Mock the HardwareSelector to prevent hardware calls."""
    with patch("src.py_umik.core.config.HardwareSelector") as mock:
        # Setup a default dummy device
        hardware_instance = mock.return_value
        hardware_instance.id = 1
        hardware_instance.name = "Dummy Device"
        hardware_instance.native_rate = 48000
        # FIX: Default to True so tests don't fail on "missing calibration file" checks
        # unless we explicitly set it to False for that specific test case.
        hardware_instance.is_default = True
        yield mock


def test_validate_args_adjusts_buffer(mock_hardware_selector):
    """Test that buffer size is adjusted to meet minimums and LUFS multiples."""
    # Force settings for predictable logic
    settings.audio.min_buffer_seconds = 3.0
    settings.audio.lufs_window_seconds = 3

    # Request too small buffer (1s)
    args = argparse.Namespace(
        device_id=None, buffer_seconds=1.0, sample_rate=48000, calibration_file=None, num_taps=1024
    )

    config = AppArgs.validate_args(args)

    # Should be raised to minimum (3.0)
    assert config.buffer_seconds == 3.0


def test_validate_args_adjusts_buffer_rounding(mock_hardware_selector):
    """Test that buffer is rounded up to match LUFS window."""
    settings.audio.min_buffer_seconds = 3.0
    settings.audio.lufs_window_seconds = 3

    # Request 4s buffer (not divisible by 3)
    args = argparse.Namespace(
        device_id=None, buffer_seconds=4.0, sample_rate=48000, calibration_file=None, num_taps=1024
    )

    config = AppArgs.validate_args(args)

    # Should be rounded up to 6.0 (next multiple of 3)
    assert config.buffer_seconds == 6.0


@patch("src.py_umik.core.config.HardwareCalibrator")
def test_validate_args_with_calibration(mock_calibrator_cls, mock_hardware_selector):
    """Test valid configuration with a non-default device and calibration file."""
    # Setup mocks
    mock_calibrator_cls.get_sensitivity_values.return_value = (-18.0, 94.0)

    # FIX: Explicitly simulate a non-default device for this test
    mock_hardware_selector.return_value.is_default = False

    args = argparse.Namespace(
        device_id=99,  # Non-default
        buffer_seconds=6.0,
        sample_rate=44100,  # Request 44.1k
        calibration_file="/path/to/cal.txt",
        num_taps=512,
    )

    config = AppArgs.validate_args(args)

    # Should use the device's native rate (48000 from mock) overriding the requested 44100
    assert config.sample_rate == 48000
    assert config.audio_calibrator is not None
    assert config.sensitivity_dbfs == -18.0
    assert config.num_taps == 512


def test_missing_calibration_file_error(mock_hardware_selector):
    """Test that error is raised if non-default device is used without calibration."""
    # FIX: Explicitly simulate a non-default device for this test
    mock_hardware_selector.return_value.is_default = False

    args = argparse.Namespace(device_id=99, buffer_seconds=6.0, sample_rate=48000, calibration_file=None, num_taps=1024)

    with pytest.raises(ValueError, match="Calibration file required"):
        AppArgs.validate_args(args)
