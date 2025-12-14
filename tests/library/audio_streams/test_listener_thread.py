"""
Unit tests for AudioStreamsListenerThread.
"""

import threading
from unittest.mock import MagicMock, patch

import pytest
import sounddevice as sd

from src.library.audio_streams.listener_thread import AudioStreamsListenerThread


@pytest.fixture
def mock_deps():
    config = MagicMock()
    config.id = 1
    config.sample_rate = 48000
    config.block_size = 1024

    q = MagicMock()
    stop = threading.Event()
    return config, q, stop


def test_listener_normal_read(mock_deps):
    """Test normal reading from stream."""
    config, q, stop = mock_deps
    listener = AudioStreamsListenerThread(config, q, stop)

    # Mock Stream
    with patch("sounddevice.InputStream") as mock_stream_cls:
        # Get the instance returned by the context manager
        mock_stream = mock_stream_cls.return_value.__enter__.return_value

        # Setup read to return data then stop
        fake_data = MagicMock()
        fake_data.ndim = 2
        fake_data.flatten.return_value = fake_data  # simplfy

        # Define side effect to stop the loop after one read
        def stop_side_effect(*args):
            stop.set()
            return (fake_data, False)  # (data, overflow)

        mock_stream.read.side_effect = stop_side_effect

        listener.run()

        # Verify put was called
        q.put_nowait.assert_called()


def test_listener_reconnects_on_error(mock_deps):
    """Test that listener attempts to reconnect on PortAudioError."""
    config, q, stop = mock_deps
    listener = AudioStreamsListenerThread(config, q, stop)
    # Speed up tests
    listener._reconnect_delay_seconds = 0.01
    listener._max_retries = 2

    with patch("sounddevice.InputStream") as mock_stream_cls:
        # 1. Create the mock for the successful attempt separately
        success_stream_mock = MagicMock()

        # 2. Configure the successful stream to break the loop immediately
        valid_stream_instance = success_stream_mock.__enter__.return_value
        # When read() is called: set stop event, then return dummy data
        valid_stream_instance.read.side_effect = lambda x: stop.set() or (MagicMock(), False)

        # 3. Assign side_effect with the Error first, then the Configured Mock
        mock_stream_cls.side_effect = [
            sd.PortAudioError("Device Lost"),  # Attempt 1: Fails
            success_stream_mock,  # Attempt 2: Succeeds
        ]

        listener.run()

        # Check that we tried twice (First failed, Second succeeded)
        assert mock_stream_cls.call_count == 2
