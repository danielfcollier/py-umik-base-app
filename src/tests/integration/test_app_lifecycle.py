"""
Integration tests for application lifecycle.
Tests startup, processing, signal handling, and graceful shutdown.

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
    AudioSink,
    OperationalMode,
    PipelineContext,
    QueueInMemoryTransport,
)


@pytest.fixture(autouse=True)
def mock_signals():
    """Disable signal registration since tests run app in background threads."""
    with patch("umik_base_app.base_thread_app.signal.signal"):
        yield


class RecordingSink(AudioSink):
    """Test sink that records all received audio chunks."""

    def __init__(self):
        self.received: list[tuple[np.ndarray, datetime]] = []
        self.call_count = 0

    def handle(self, ctx: PipelineContext) -> None:
        self.received.append((ctx.audio, ctx.timestamp))
        self.call_count += 1


@pytest.fixture
def fake_audio_chunks():
    """Generate fake audio data for testing."""
    chunks = []
    for _ in range(5):
        # 0.1 seconds of audio at 48kHz
        chunk = np.random.randn(4800).astype(np.float32) * 0.1
        timestamp = datetime.now()
        chunks.append((chunk, timestamp))
    return chunks


@pytest.fixture
def test_transport(fake_audio_chunks):
    """Pre-populated transport with fake audio."""
    transport = QueueInMemoryTransport()
    for chunk, timestamp in fake_audio_chunks:
        transport.send((chunk, timestamp))
    return transport


@pytest.fixture
def recording_sink():
    """Sink that captures processed audio for assertions."""
    return RecordingSink()


@pytest.fixture
def consumer_config():
    """AppConfig in CONSUMER mode (no hardware needed)."""
    return AppConfig(
        sample_rate=48000.0,
        buffer_seconds=0.1,
        run_mode=OperationalMode.CONSUMER,
        audio_device=None,
    )


@pytest.mark.integration
@pytest.mark.timeout(5)
def test_app_lifecycle_processes_audio_and_shuts_down(
    consumer_config,
    test_transport,
    recording_sink,
    fake_audio_chunks,
):
    """
    Integration test for full application lifecycle:
    1. App starts in background thread
    2. Processes pre-loaded audio chunks
    3. Shuts down gracefully on signal
    4. All chunks are processed
    """
    # --- 1. Setup Pipeline with Recording Sink ---
    pipeline = AudioPipeline(sample_rate=consumer_config.sample_rate)
    pipeline.add_sink(recording_sink)

    # --- 2. Create App with Injected Transport ---
    app = AudioBaseApp(
        app_config=consumer_config,
        pipeline=pipeline,
        transport=test_transport,
    )

    # --- 3. Run App in Background Thread ---
    app_thread = threading.Thread(target=app.run, name="TestAppThread")
    app_thread.start()

    # --- 4. Wait for Processing ---
    max_wait = 2.0
    poll_interval = 0.05
    elapsed = 0.0

    while recording_sink.call_count < len(fake_audio_chunks) and elapsed < max_wait:
        time.sleep(poll_interval)
        elapsed += poll_interval

    # --- 5. Trigger Shutdown ---
    app.shutdown()

    # --- 6. Wait for Clean Termination ---
    app_thread.join(timeout=2.0)

    # --- 7. Assertions ---
    assert recording_sink.call_count == len(fake_audio_chunks)
    assert not app_thread.is_alive()
    assert app._stop_event.is_set()

    for thread in app._threads:
        assert not thread.is_alive()


@pytest.mark.integration
@pytest.mark.timeout(5)
def test_app_handles_empty_queue_gracefully(consumer_config, recording_sink):
    """
    Test that app handles empty transport without hanging.
    Should exit cleanly when shutdown is called with no data.
    """
    transport = QueueInMemoryTransport()

    pipeline = AudioPipeline(sample_rate=consumer_config.sample_rate)
    pipeline.add_sink(recording_sink)

    app = AudioBaseApp(
        app_config=consumer_config,
        pipeline=pipeline,
        transport=transport,
    )

    app_thread = threading.Thread(target=app.run, name="TestAppThread")
    app_thread.start()

    time.sleep(0.1)

    app.shutdown()

    app_thread.join(timeout=2.0)

    assert not app_thread.is_alive()
    assert recording_sink.call_count == 0


@pytest.mark.integration
@pytest.mark.timeout(5)
def test_app_shutdown_is_responsive(consumer_config, recording_sink):
    """
    Test that shutdown is responsive even with queued data.
    The app should terminate quickly after shutdown() is called.
    """
    transport = QueueInMemoryTransport()

    # Load chunks
    for _ in range(50):
        chunk = np.zeros(4800, dtype=np.float32)
        transport.send((chunk, datetime.now()))

    pipeline = AudioPipeline(sample_rate=consumer_config.sample_rate)
    pipeline.add_sink(recording_sink)

    app = AudioBaseApp(
        app_config=consumer_config,
        pipeline=pipeline,
        transport=transport,
    )

    app_thread = threading.Thread(target=app.run, name="TestAppThread")
    app_thread.start()

    # Let it start processing
    time.sleep(0.05)

    # Shutdown and measure termination time
    shutdown_start = time.time()
    app.shutdown()
    app_thread.join(timeout=2.0)
    shutdown_duration = time.time() - shutdown_start

    # Key assertions: clean termination
    assert not app_thread.is_alive()
    assert app._stop_event.is_set()

    # Shutdown should be responsive (< 1 second)
    assert shutdown_duration < 1.0
