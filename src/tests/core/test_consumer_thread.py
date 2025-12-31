"""
Unit tests for ConsumerThread.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

import queue
import threading
from unittest.mock import MagicMock

from umik_base_app.core.consumer_thread import ConsumerThread


def test_consumer_processes_queue():
    """Test that consumer fetches items via transport and executes pipeline."""
    mock_transport = MagicMock()  # This replaces the old mock_queue
    mock_pipeline = MagicMock()
    stop_event = threading.Event()

    consumer = ConsumerThread(
        transport=mock_transport, stop_event=stop_event, pipeline=mock_pipeline, consumer_queue_timeout_seconds=0.1
    )

    # Setup transport side effects:
    # 1. Return valid data (chunk, timestamp)
    # 2. Raise queue.Empty to simulate timeout
    chunk = MagicMock()
    timestamp = "12:00:00"

    # FIX: Mock .recv() instead of .get()
    mock_transport.recv.side_effect = [
        (chunk, timestamp),
        queue.Empty,
    ]

    # Run in a separate thread briefly
    t = threading.Thread(target=consumer.run)
    t.start()

    # Wait for processing then stop
    t.join(timeout=0.2)
    stop_event.set()

    # Verify pipeline was called with correct args
    mock_pipeline.execute.assert_called_with(chunk, timestamp)


def test_consumer_handles_pipeline_error():
    """Test that consumer keeps running if pipeline fails."""
    mock_transport = MagicMock()
    mock_pipeline = MagicMock()
    stop_event = threading.Event()

    consumer = ConsumerThread(
        transport=mock_transport, stop_event=stop_event, pipeline=mock_pipeline, consumer_queue_timeout_seconds=0.1
    )

    # Pipeline raises error on execution
    mock_pipeline.execute.side_effect = Exception("Processing Error")

    # Transport returns valid data
    mock_transport.recv.return_value = (MagicMock(), "ts")

    # Start thread
    t = threading.Thread(target=consumer.run)
    t.start()

    # Stop quickly
    stop_event.set()
    t.join(timeout=0.1)

    # Should have called execute (and logged error internally), but not crashed
    assert mock_pipeline.execute.called
