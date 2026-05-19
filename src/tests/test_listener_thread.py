"""
Unit tests for ListenerThread.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

from contextlib import contextmanager
from unittest.mock import MagicMock, patch, sentinel

import pytest
import sounddevice as sd

from umik_base_app.listener_thread import ListenerThread


@contextmanager
def _noop_ctx():
    yield


@pytest.fixture
def mock_deps(stop_event):
    config = MagicMock()
    config.id = 1
    config.name = "Test Device (hw:0,0)"
    config.sample_rate = 48000
    config.block_size = 1024

    transport = MagicMock()
    return config, transport, stop_event


@patch("umik_base_app.listener_thread.datetime")
@patch("umik_base_app.listener_thread.HardwareSelector")
def test_listener_normal_read(mock_hw_selector, mock_datetime_module, mock_deps):
    """Test that audio data received via callback is forwarded to the transport."""
    config, transport, stop = mock_deps
    mock_hw_selector.find_device_by_name.return_value = config.id
    mock_datetime_module.now.return_value = sentinel.timestamp

    listener = ListenerThread(config, transport, stop)
    captured = {}

    def fake_input_stream(**kwargs):
        captured["callback"] = kwargs["callback"]
        return MagicMock()

    with patch.object(ListenerThread, "_suppress_alsa_stderr", staticmethod(_noop_ctx)):
        with patch("sounddevice.InputStream", side_effect=fake_input_stream):
            # Simulate one callback firing then stop
            def on_start(mock_stream):
                mock_stream.start.side_effect = _fire_callback_then_stop

            def _fire_callback_then_stop():
                status = MagicMock()
                status.input_overflow = False
                mock_audio = MagicMock()
                captured["callback"](mock_audio, 4096, None, status)
                stop.set()

            with patch("sounddevice.InputStream", side_effect=fake_input_stream) as mock_cls:
                mock_stream = MagicMock()
                mock_cls.side_effect = lambda **kw: (captured.update({"callback": kw["callback"]}) or mock_stream)
                mock_stream.start.side_effect = _fire_callback_then_stop

                listener.run()

    transport.send.assert_called_once()
    call_args = transport.send.call_args[0][0]
    assert call_args[1] == sentinel.timestamp


@patch("umik_base_app.listener_thread.HardwareSelector")
def test_listener_reconnects_on_error(mock_hw_selector, mock_deps):
    """Test that listener attempts to reconnect on PortAudioError."""
    config, transport, stop = mock_deps
    mock_hw_selector.find_device_by_name.return_value = config.id

    listener = ListenerThread(config, transport, stop)
    listener._reconnect_delay_seconds = 0.01
    listener._max_retries = 2

    success_stream = MagicMock()
    success_stream.start.side_effect = stop.set

    streams = [sd.PortAudioError("Device Lost"), success_stream]

    def fake_input_stream(**kwargs):
        result = streams.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    with patch.object(ListenerThread, "_suppress_alsa_stderr", staticmethod(_noop_ctx)):
        with patch("sounddevice.InputStream", side_effect=fake_input_stream) as mock_cls:
            listener.run()
            assert mock_cls.call_count == 2
