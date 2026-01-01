"""
Tests for AppConfig argument parsing and validation.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

import argparse
import os
from unittest.mock import patch, sentinel

import pytest

from umik_base_app import AppArgs
from umik_base_app.settings import get_settings

settings = get_settings()


@pytest.fixture
def mock_hardware_selector():
    """Mock the HardwareSelector to prevent hardware calls."""
    # Patch where it is imported in 'app_args.py' to ensure isolation
    with patch("umik_base_app.app_args.HardwareSelector") as mock:
        # Setup a default dummy device
        hardware_instance = mock.return_value
        hardware_instance.id = 1
        hardware_instance.name = "Dummy Device"
        hardware_instance.native_rate = 48000
        hardware_instance.is_default = True
        yield mock


@patch.dict(os.environ, {"CALIBRATION_FILE": ""})
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
        default=False,
        producer=False,
        consumer=False,
        zmq_host=sentinel.zmq_host,
        zmq_port=sentinel.zmq_port,
    )

    config = AppArgs.validate_args(args)

    # Should be raised to minimum (3.0)
    assert config.buffer_seconds == 3.0


@patch.dict(os.environ, {"CALIBRATION_FILE": ""})
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
        default=False,
        producer=False,
        consumer=False,
        zmq_host=sentinel.zmq_host,
        zmq_port=sentinel.zmq_port,
    )

    config = AppArgs.validate_args(args)

    # Should be rounded up to 6.0 (next multiple of 3)
    assert config.buffer_seconds == 6.0


@patch("umik_base_app.app_args.CalibratorTransformer")
def test_validate_args_with_calibration(mock_calibrator_cls, mock_hardware_selector):
    """Test valid configuration with a non-default device and calibration file."""
    # Arrange
    mock_calibrator_cls.get_sensitivity_values.return_value = (
        sentinel.sensitivity_dbfs,
        sentinel.reference_dbspl,
    )

    # Explicitly simulate a non-default device for this test
    # Note: native_rate must be a number because the code performs float() conversion on it
    mock_hardware_selector.return_value.is_default = False
    mock_hardware_selector.return_value.native_rate = 48000

    args = argparse.Namespace(
        device_id=sentinel.device_id,
        buffer_seconds=6.0,
        sample_rate=44100,
        calibration_file=sentinel.cal_file,
        num_taps=sentinel.num_taps,
        default=False,
        producer=False,
        consumer=False,
        zmq_host=sentinel.zmq_host,
        zmq_port=sentinel.zmq_port,
    )

    # Act
    config = AppArgs.validate_args(args)

    # Assert
    mock_hardware_selector.assert_called_with(target_id=sentinel.device_id)

    # Should use the device's native rate (48000) overriding the requested 44100
    assert config.sample_rate == 48000

    mock_calibrator_cls.get_sensitivity_values.assert_called_once_with(
        sentinel.cal_file,
        settings.HARDWARE.NOMINAL_SENSITIVITY_DBFS,
        settings.HARDWARE.REFERENCE_DBSPL,
    )
    mock_calibrator_cls.assert_called_once_with(
        calibration_file_path=sentinel.cal_file, sample_rate=48000, num_taps=sentinel.num_taps
    )

    assert config.audio_calibrator == mock_calibrator_cls.return_value
    assert config.sensitivity_dbfs == sentinel.sensitivity_dbfs
    assert config.reference_dbspl == sentinel.reference_dbspl
    assert config.num_taps == sentinel.num_taps
    assert config.zmq_host == sentinel.zmq_host
    assert config.zmq_port == sentinel.zmq_port


@patch.dict(os.environ, {"CALIBRATION_FILE": ""})
def test_no_calibration_file_allows_uncalibrated_setup(mock_hardware_selector):
    """
    Test that no error is raised if a non-default device is used without calibration.
    """
    mock_hardware_selector.return_value.is_default = False

    args = argparse.Namespace(
        device_id=sentinel.device_id,
        buffer_seconds=6.0,
        sample_rate=48000,
        calibration_file=None,
        num_taps=sentinel.num_taps,
        default=False,
        producer=False,
        consumer=False,
        zmq_host=sentinel.zmq_host,
        zmq_port=sentinel.zmq_port,
    )

    config = AppArgs.validate_args(args)

    assert config.audio_calibrator is None

    assert config.audio_device == mock_hardware_selector.return_value
    assert config.zmq_host == sentinel.zmq_host
    assert config.zmq_port == sentinel.zmq_port
