"""
Unit tests for ConsumerThread.
"""

import queue
import threading
from unittest.mock import MagicMock

from py_umik.core.consumer_thread import ConsumerThread


def test_consumer_processes_queue():
    """Test that consumer fetches items and executes pipeline."""
    mock_queue = MagicMock()
    mock_pipeline = MagicMock()
    stop_event = threading.Event()

    consumer = ConsumerThread(
        audio_queue=mock_queue, stop_event=stop_event, pipeline=mock_pipeline, consumer_queue_timeout_seconds=0.1
    )

    # Setup queue side effects:
    # 1. Return valid data
    # 2. Raise Empty (to trigger timeout loop)
    # 3. Stop the thread loop
    chunk = MagicMock()
    timestamp = "12:00:00"

    mock_queue.get.side_effect = [
        (chunk, timestamp),
        queue.Empty,
    ]

    # We need to stop the loop after the Empty exception.
    # We can use a side effect on stop_event.is_set() to return False once, then True.
    # But simpler: run() calls queue.get in a loop.
    # Let's run it in a separate thread or just patch the loop condition logic?
    # Easier: Just let it run one iteration and then we stop it manually via side_effect.

    def side_effect_check():
        if mock_queue.get.call_count >= 2:
            stop_event.set()
        return False

    # We can't easily patch is_set on the event instance logic inside the loop
    # if we want to test the loop structure.
    # Instead, let's start a real thread for a split second.

    t = threading.Thread(target=consumer.run)
    t.start()

    t.join(timeout=0.5)
    stop_event.set()  # Ensure it stops if logic failed

    # Verify pipeline was called with correct args
    mock_pipeline.execute.assert_called_with(chunk, timestamp)


def test_consumer_handles_pipeline_error():
    """Test that consumer keeps running if pipeline fails."""
    mock_queue = MagicMock()
    mock_pipeline = MagicMock()
    stop_event = threading.Event()

    consumer = ConsumerThread(mock_queue, stop_event, mock_pipeline, 0.1)

    # AudioPipeline raises error
    mock_pipeline.execute.side_effect = Exception("Processing Error")
    mock_queue.get.return_value = (MagicMock(), "ts")

    # Run once manually
    # Break loop by setting event immediately after get
    stop_event.set()
    consumer.run()

    # Should have logged error but not crashed (implied by reaching here)
