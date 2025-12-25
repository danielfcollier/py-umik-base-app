"""
Unit tests for HardwareSelector.
Mocks the sounddevice library to avoid hardware dependencies.
"""

from unittest.mock import patch

import pytest

from src.py_umik.hardware.selector import HardwareSelector

# Mock device list returned by sd.query_devices()
MOCK_DEVICES = [
    {
        "name": "Default Mic",
        "index": 0,
        "max_input_channels": 1,
        "default_samplerate": 44100.0,
    },
    {
        "name": "UMIK-1",
        "index": 1,
        "max_input_channels": 1,
        "default_samplerate": 48000.0,
    },
    {
        "name": "Output Only",
        "index": 2,
        "max_input_channels": 0,  # Should be ignored
        "default_samplerate": 48000.0,
    },
]


@pytest.fixture
def mock_sounddevice():
    """Mock sounddevice query_devices and default attribute."""
    with patch("src.py_umik.hardware.selector.sd") as mock_sd:
        mock_sd.query_devices.return_value = MOCK_DEVICES
        # Mock sd.default.device = [input_id, output_id]
        mock_sd.default.device = [0, 2]
        yield mock_sd


def test_select_default_device(mock_sounddevice):
    """Test selecting the default device when target_id is None."""
    selector = HardwareSelector(target_id=None)

    assert selector.id == 0
    assert selector.name == "Default Mic"
    assert selector.is_default is False  # Name is "Default Mic", not "default"
    assert selector.native_rate == 44100.0


def test_select_specific_device(mock_sounddevice):
    """Test selecting a specific device by ID."""
    selector = HardwareSelector(target_id=1)

    assert selector.id == 1
    assert selector.name == "UMIK-1"
    assert selector.native_rate == 48000.0


def test_device_not_found_exits(mock_sounddevice):
    """Test that selecting a non-existent device raises SystemExit (via exit(1))."""
    # ID 99 does not exist in MOCK_DEVICES
    with pytest.raises(SystemExit) as excinfo:
        HardwareSelector(target_id=99)

    assert excinfo.value.code == 1


def test_show_audio_devices(mock_sounddevice):
    """Test the utility method that logs available devices."""
    with patch("src.py_umik.hardware.selector.logger") as mock_logger:
        HardwareSelector.show_audio_devices(selected_id=1)

        # Verify it logged the devices
        assert mock_logger.info.called
        # Check if UMIK-1 was logged with the selection marker '>'
        logs = [call.args[0] for call in mock_logger.info.call_args_list]
        assert any("> ID 1" in log for log in logs)


def test_unexpected_error_raises(mock_sounddevice):
    """Test that unexpected exceptions bubble up."""
    mock_sounddevice.query_devices.side_effect = Exception("Boom")

    with pytest.raises(Exception, match="Boom"):
        HardwareSelector(target_id=0)
