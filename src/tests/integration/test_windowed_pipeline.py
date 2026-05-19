"""
End-to-end integration tests for the windowed AudioMetricsSink in a full pipeline.

Verifies that audio flowing through the real transport → ConsumerThread →
AudioPipeline → AudioMetricsSink chain produces exactly the right number of
windows, each of the exact target length, with overshoot carried into the
next window (no samples discarded).

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

import threading
import time
from datetime import datetime
from unittest.mock import patch

import numpy as np
import pytest

from umik_base_app import (
    AppConfig,
    AudioBaseApp,
    AudioPipeline,
    OperationalMode,
    QueueInMemoryTransport,
)
from umik_base_app.apps.real_time_meter import AudioMetricsSink

# ── helpers ──────────────────────────────────────────────────────────────────

SAMPLE_RATE = 48000

# 1 000-sample window (~20ms) keeps the test fast while exercising real arithmetic.
WINDOW_SAMPLES = 1000
WINDOW_SECONDS = WINDOW_SAMPLES / SAMPLE_RATE

# 700-sample chunks don't divide evenly into 1 000-sample windows:
#   chunk 1:  700 accumulated → no emit
#   chunk 2: 1400 accumulated → emit window 1 (1000), carry 400
#   chunk 3: 1100 accumulated → emit window 2 (1000), carry 100
#   chunk 4:  800 accumulated → no emit
#   chunk 5: 1500 accumulated → emit window 3 (1000), carry 500
CHUNK_SIZE = 700
NUM_CHUNKS = 5
EXPECTED_WINDOWS = 3
EXPECTED_LEFTOVER = NUM_CHUNKS * CHUNK_SIZE - EXPECTED_WINDOWS * WINDOW_SAMPLES  # 500


def _make_sink() -> AudioMetricsSink:
    """Create an AudioMetricsSink wired to a tiny test window."""
    with patch("umik_base_app.apps.real_time_meter.settings") as s:
        s.METRICS.INTERVAL_SECONDS = WINDOW_SECONDS
        sink = AudioMetricsSink(sample_rate=SAMPLE_RATE)
    sink._target_samples = WINDOW_SAMPLES
    return sink


def _make_app(sink: AudioMetricsSink, transport: QueueInMemoryTransport) -> AudioBaseApp:
    pipeline = AudioPipeline(sample_rate=SAMPLE_RATE)
    pipeline.add_sink(sink)
    config = AppConfig(
        sample_rate=SAMPLE_RATE,
        buffer_seconds=0.1,
        run_mode=OperationalMode.CONSUMER,
        audio_device=None,
    )
    return AudioBaseApp(app_config=config, pipeline=pipeline, transport=transport)


# ── fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def mock_signals():
    with patch("umik_base_app.base_thread_app.signal.signal"):
        yield


# ── tests ─────────────────────────────────────────────────────────────────────


@pytest.mark.integration
@pytest.mark.timeout(10)
def test_windowed_sink_emits_correct_number_of_windows():
    """
    Chunks fed through the full pipeline produce exactly EXPECTED_WINDOWS
    complete windows.  No extra or missing fires.
    """
    sink = _make_sink()
    emitted = []
    sink._process_and_log = lambda audio, *_a, **_kw: emitted.append(len(audio))

    transport = QueueInMemoryTransport()
    for _ in range(NUM_CHUNKS):
        transport.send((np.zeros(CHUNK_SIZE, dtype=np.float32), datetime.now()))

    app = _make_app(sink, transport)
    app_thread = threading.Thread(target=app.run, name="TestAppThread")
    app_thread.start()

    deadline = time.time() + 5.0
    while len(emitted) < EXPECTED_WINDOWS and time.time() < deadline:
        time.sleep(0.01)

    app.shutdown()
    app_thread.join(timeout=2.0)

    assert len(emitted) == EXPECTED_WINDOWS


@pytest.mark.integration
@pytest.mark.timeout(10)
def test_windowed_sink_each_window_is_exact_target_length():
    """
    Every emitted window is exactly WINDOW_SAMPLES long — the overshoot
    is trimmed, never inflated.
    """
    sink = _make_sink()
    emitted = []
    sink._process_and_log = lambda audio, *_a, **_kw: emitted.append(len(audio))

    transport = QueueInMemoryTransport()
    for _ in range(NUM_CHUNKS):
        transport.send((np.zeros(CHUNK_SIZE, dtype=np.float32), datetime.now()))

    app = _make_app(sink, transport)
    app_thread = threading.Thread(target=app.run, name="TestAppThread")
    app_thread.start()

    deadline = time.time() + 5.0
    while len(emitted) < EXPECTED_WINDOWS and time.time() < deadline:
        time.sleep(0.01)

    app.shutdown()
    app_thread.join(timeout=2.0)

    assert all(n == WINDOW_SAMPLES for n in emitted), f"Window lengths: {emitted}"


@pytest.mark.integration
@pytest.mark.timeout(10)
def test_windowed_sink_overshoot_is_not_discarded():
    """
    After all chunks are processed, the samples that overshot the last
    window boundary are still in the buffer — none were silently dropped.

    Total input: NUM_CHUNKS × CHUNK_SIZE = 3500 samples
    Complete windows: 3 × 1000 = 3000 samples
    Expected leftover: 500 samples
    """
    sink = _make_sink()
    sink._process_and_log = lambda *_a, **_kw: None  # suppress real metric calls

    transport = QueueInMemoryTransport()
    for _ in range(NUM_CHUNKS):
        transport.send((np.zeros(CHUNK_SIZE, dtype=np.float32), datetime.now()))

    app = _make_app(sink, transport)
    app_thread = threading.Thread(target=app.run, name="TestAppThread")
    app_thread.start()

    # Wait until the transport is drained
    deadline = time.time() + 5.0
    while transport._queue.qsize() > 0 and time.time() < deadline:
        time.sleep(0.01)
    time.sleep(0.05)  # let the last chunk complete processing

    app.shutdown()
    app_thread.join(timeout=2.0)

    assert sink._accumulated_samples == EXPECTED_LEFTOVER
