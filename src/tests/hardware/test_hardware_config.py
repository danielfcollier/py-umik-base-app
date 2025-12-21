"""
Unit tests for HardwareConfig.
"""

from unittest.mock import MagicMock

from src.py_umik.hardware.config import HardwareConfig


def test_audio_device_config_initialization():
    """Test that block_size is calculated correctly from sample_rate and buffer."""
    # Mock the selector dependency
    mock_selector = MagicMock()
    mock_selector.id = 1
    mock_selector.native_rate = 48000

    config = HardwareConfig(
        target_audio_device=mock_selector, sample_rate=48000, buffer_seconds=2.0, dtype="float32", high_priority=True
    )

    assert config.id == 1
    assert config.sample_rate == 48000
    assert config.buffer_seconds == 2.0
    # Block size = sample_rate * buffer_seconds
    assert config.block_size == 96000
    assert config.dtype == "float32"
    assert config.high_priority is True


def test_audio_device_config_defaults():
    """Test defaults via settings (if applied) or direct init."""
    mock_selector = MagicMock()
    mock_selector.id = 0
    mock_selector.native_rate = 44100

    # Assuming the class allows None for optional args or handles them via settings
    config = HardwareConfig(target_audio_device=mock_selector, sample_rate=44100, buffer_seconds=1.0)

    assert config.block_size == 44100
    # Check default behavior if your class uses settings defaults for dtype/priority
    # assert config.high_priority is False (depending on your implementation)
