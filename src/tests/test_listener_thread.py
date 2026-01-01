"""
Unit tests for ListenerThread.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

import threading
from unittest.mock import MagicMock, patch, sentinel

import pytest
import sounddevice as sd

from umik_base_app.listener_thread import ListenerThread


@pytest.fixture
def mock_deps():
    config = MagicMock()
    # Use sentinel for ID to verify exact pass-through
    config.id = sentinel.device_id
    config.sample_rate = 48000
    config.block_size = 1024

    q = MagicMock()
    stop = threading.Event()
    return config, q, stop


@patch("umik_base_app.listener_thread.DatetimeStamp")
def test_listener_normal_read(mock_datetime, mock_deps):
    """Test normal reading from stream."""
    config, q, stop = mock_deps
    listener = ListenerThread(config, q, stop)

    # Setup Timestamp mock
    mock_datetime.get.return_value = sentinel.timestamp

    # Mock Stream
    with patch("sounddevice.InputStream") as mock_stream_cls:
        # Get the instance returned by the context manager
        mock_stream = mock_stream_cls.return_value.__enter__.return_value

        # We use a MagicMock to simulate the array properties required by logic (e.g., .ndim)
        mock_audio_data = MagicMock()
        mock_audio_data.ndim = 1  # Pretend it is already 1D to skip flattening

        # Define side effect to allow one successful read, then stop on the next
        call_counter = 0

        def smart_side_effect(*args):
            nonlocal call_counter
            call_counter += 1
            if call_counter > 1:
                stop.set()
            # Return (data, overflow_flag)
            return (mock_audio_data, False)

        mock_stream.read.side_effect = smart_side_effect

        listener.run()

        # Verify put was called with (audio_chunk, timestamp)
        # The previous failure was expecting (audio_chunk, False), which was incorrect.
        q.send.assert_called_with((mock_audio_data, sentinel.timestamp))


def test_listener_reconnects_on_error(mock_deps):
    """Test that listener attempts to reconnect on PortAudioError."""
    config, q, stop = mock_deps
    listener = ListenerThread(config, q, stop)
    # Speed up tests
    listener._reconnect_delay_seconds = 0.01
    listener._max_retries = 2

    with patch("sounddevice.InputStream") as mock_stream_cls:
        # 1. Create the mock for the successful attempt separately
        success_stream_mock = MagicMock()

        # 2. Configure the successful stream to break the loop immediately
        valid_stream_instance = success_stream_mock.__enter__.return_value

        mock_audio_data = MagicMock()
        mock_audio_data.ndim = 1

        # On the successful stream, just set stop immediately to exit loop clean
        # We also need to patch DatetimeStamp here if we want strictly clean logs,
        # but for this test we only care about the reconnection logic (mock_stream_cls calls).
        valid_stream_instance.read.side_effect = lambda x: stop.set() or (mock_audio_data, False)

        # 3. Assign side_effect with the Error first, then the Configured Mock
        mock_stream_cls.side_effect = [
            sd.PortAudioError("Device Lost"),  # Attempt 1: Fails
            success_stream_mock,  # Attempt 2: Succeeds
        ]

        listener.run()

        # Check that we tried twice (First failed, Second succeeded)
        assert mock_stream_cls.call_count == 2
