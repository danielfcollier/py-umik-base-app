"""
Unit tests for HardwareConfig.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

from unittest.mock import MagicMock, sentinel

from umik_base_app import HardwareConfig


def test_audio_device_config_initialization():
    """Test that block_size is calculated correctly from sample_rate and buffer."""
    # Mock the selector dependency
    mock_selector = MagicMock()
    mock_selector.id = sentinel.device_id
    # native_rate is unused in init if sample_rate is provided explicitly,
    # but we mock it just in case logic changes.
    mock_selector.native_rate = 48000

    config = HardwareConfig(
        target_audio_device=mock_selector,
        sample_rate=48000,
        buffer_seconds=2.0,
        dtype=sentinel.dtype,
        high_priority=sentinel.high_priority,
    )

    assert config.id == sentinel.device_id
    assert config.sample_rate == 48000
    assert config.buffer_seconds == 2.0
    # Block size = sample_rate * buffer_seconds
    assert config.block_size == 96000
    assert config.dtype == sentinel.dtype
    assert config.high_priority == sentinel.high_priority


def test_audio_device_config_defaults():
    """Test defaults via settings (if applied) or direct init."""
    mock_selector = MagicMock()
    mock_selector.id = sentinel.device_id_default
    mock_selector.native_rate = 44100

    # Assuming the class allows None for optional args or handles them via settings
    config = HardwareConfig(target_audio_device=mock_selector, sample_rate=44100, buffer_seconds=1.0)

    assert config.id == sentinel.device_id_default
    assert config.block_size == 44100
