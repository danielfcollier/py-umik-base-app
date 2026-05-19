"""
End-to-end integration tests for ListenerThread disconnect detection and reconnect.

Exercises the real thread lifecycle: silence-based disconnect detection via the
heartbeat loop, reconnection after transient failure, and unlimited-retry behaviour
when _max_retries is None.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

import threading
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import sounddevice as sd

from umik_base_app import QueueInMemoryTransport
from umik_base_app.listener_thread import ListenerThread


@contextmanager
def _noop_ctx():
    yield


def _make_config():
    cfg = MagicMock()
    cfg.id = 1
    cfg.name = "Test Device (hw:0,0)"
    cfg.sample_rate = 48000
    cfg.dtype = "float32"
    return cfg


def _make_listener(stop: threading.Event, transport: QueueInMemoryTransport) -> ListenerThread:
    listener = ListenerThread(_make_config(), transport, stop)
    listener._reconnect_delay_seconds = 0.05  # fast reconnect wait
    listener._silence_check_interval = 0.05  # fast silence poll
    return listener


# ── tests ─────────────────────────────────────────────────────────────────────


@pytest.mark.integration
@pytest.mark.timeout(10)
def test_listener_detects_silence_and_reconnects():
    """
    When audio stops arriving, the heartbeat loop detects the silence,
    closes the stream, and opens a new one.

    Flow:
      stream 1 — callback fires once, then silence exceeds threshold → reconnect
      stream 2 — start() sets stop_event, listener exits cleanly
    """
    stop = threading.Event()
    transport = QueueInMemoryTransport()
    listener = _make_listener(stop, transport)

    stream_open_count = [0]
    captured_callback = [None]

    def fake_input_stream(**kwargs):
        stream_open_count[0] += 1
        captured_callback[0] = kwargs["callback"]
        stream = MagicMock()

        if stream_open_count[0] == 1:

            def fire_once_then_go_silent():
                status = MagicMock()
                status.input_overflow = False
                captured_callback[0](np.zeros(4096, dtype="float32"), 4096, None, status)
                # No further callbacks — silence timeout will trigger

            stream.start.side_effect = fire_once_then_go_silent
        else:
            stream.start.side_effect = stop.set  # clean exit on reconnect

        return stream

    with patch.object(ListenerThread, "_suppress_alsa_stderr", staticmethod(_noop_ctx)):
        with patch("sounddevice.InputStream", side_effect=fake_input_stream):
            t = threading.Thread(target=listener.run)
            t.start()
            t.join(timeout=8.0)

    assert not t.is_alive(), "ListenerThread did not exit"
    assert stream_open_count[0] == 2, f"Expected 2 stream opens, got {stream_open_count[0]}"


@pytest.mark.integration
@pytest.mark.timeout(10)
def test_listener_forwards_audio_to_transport_before_disconnect():
    """
    Audio received via callback before a disconnect is forwarded to the
    transport and can be consumed downstream.
    """
    stop = threading.Event()
    transport = QueueInMemoryTransport()
    listener = _make_listener(stop, transport)

    captured_callback = [None]

    def fake_input_stream(**kwargs):
        captured_callback[0] = kwargs["callback"]
        stream = MagicMock()

        def fire_then_stop():
            status = MagicMock()
            status.input_overflow = False
            audio = np.ones(4096, dtype="float32") * 0.5
            captured_callback[0](audio, 4096, None, status)
            stop.set()

        stream.start.side_effect = fire_then_stop
        return stream

    with patch.object(ListenerThread, "_suppress_alsa_stderr", staticmethod(_noop_ctx)):
        with patch("sounddevice.InputStream", side_effect=fake_input_stream):
            t = threading.Thread(target=listener.run)
            t.start()
            t.join(timeout=5.0)

    assert not t.is_alive()
    chunk, timestamp = transport.recv(timeout_seconds=1.0)
    assert len(chunk) == 4096
    assert timestamp is not None


@pytest.mark.integration
@pytest.mark.timeout(15)
def test_listener_unlimited_retries_continue_past_finite_limit():
    """
    When _max_retries is None, the listener keeps retrying after repeated
    failures instead of giving up.  Here we allow N failures and verify
    the listener attempts N+1 opens, stopping only when stop_event is set.
    """
    FAILURES = 4

    stop = threading.Event()
    transport = QueueInMemoryTransport()
    listener = _make_listener(stop, transport)
    listener._max_retries = None  # unlimited

    attempt = [0]

    def fake_input_stream(**kwargs):
        attempt[0] += 1
        if attempt[0] <= FAILURES:
            raise sd.PortAudioError("Simulated failure")
        # On success: set stop so the listener exits
        stream = MagicMock()
        stream.start.side_effect = stop.set
        return stream

    with patch.object(ListenerThread, "_suppress_alsa_stderr", staticmethod(_noop_ctx)):
        with patch("sounddevice.InputStream", side_effect=fake_input_stream):
            t = threading.Thread(target=listener.run)
            t.start()
            t.join(timeout=10.0)

    assert not t.is_alive(), "ListenerThread did not exit"
    assert attempt[0] == FAILURES + 1, f"Expected {FAILURES + 1} attempts with unlimited retries, got {attempt[0]}"


@pytest.mark.integration
@pytest.mark.timeout(10)
def test_listener_retry_count_resets_after_successful_reconnect():
    """
    After a successful reconnect the internal retry counter resets to zero,
    so a later disconnect starts counting from 1 again (not accumulating
    across sessions).
    """
    stop = threading.Event()
    transport = QueueInMemoryTransport()
    listener = _make_listener(stop, transport)
    listener._max_retries = 2

    attempt = [0]
    captured_callback = [None]

    def fake_input_stream(**kwargs):
        attempt[0] += 1
        captured_callback[0] = kwargs["callback"]
        stream = MagicMock()

        if attempt[0] == 1:
            # Fail on first try
            raise sd.PortAudioError("First failure")

        if attempt[0] == 2:
            # Second attempt succeeds: fire callback once, then go silent → triggers reconnect
            def fire_once():
                status = MagicMock()
                status.input_overflow = False
                captured_callback[0](np.zeros(4096, dtype="float32"), 4096, None, status)

            stream.start.side_effect = fire_once

        if attempt[0] == 3:
            # Third attempt (after second disconnect): immediately stop
            stream.start.side_effect = stop.set

        return stream

    with patch.object(ListenerThread, "_suppress_alsa_stderr", staticmethod(_noop_ctx)):
        with patch("sounddevice.InputStream", side_effect=fake_input_stream):
            t = threading.Thread(target=listener.run)
            t.start()
            t.join(timeout=8.0)

    # Listener should have made 3 attempts total and exited cleanly (not hit max_retries=2)
    assert not t.is_alive(), "ListenerThread did not exit"
    assert attempt[0] == 3
