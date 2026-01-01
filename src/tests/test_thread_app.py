"""
Unit tests for BaseThreadApp.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

import threading
from unittest.mock import MagicMock, patch

from umik_base_app.base_thread_app import BaseThreadApp


class ConcreteApp(BaseThreadApp):
    """Helper class to instantiate abstract ThreadApp."""

    def _setup_threads(self):
        # Create a dummy thread
        t = threading.Thread(target=lambda: None)
        self._threads.append(t)


def test_shutdown_sets_event():
    """Test that shutdown sets the stop event."""
    app = ConcreteApp()
    assert not app._stop_event.is_set()

    app.shutdown()
    assert app._stop_event.is_set()


def test_thread_guard_handles_exception():
    """Test that _thread_guard catches exceptions and triggers shutdown."""
    app = ConcreteApp()

    # Define a target that raises an exception
    def bad_worker():
        raise ValueError("Worker Failed")

    # Wrap it
    guarded = app._thread_guard(bad_worker)

    # Run it
    guarded()

    # Verify app is shutting down
    assert app._stop_event.is_set()

    # Verify error was queued
    error = app._error_queue.get()
    assert isinstance(error, ValueError)
    assert str(error) == "Worker Failed"


@patch("signal.signal")
def test_run_starts_threads(mock_signal):
    """Test the run loop (mocking wait to avoid blocking)."""
    app = ConcreteApp()

    # Mock stop_event.wait to return immediately so run() finishes
    app._stop_event.wait = MagicMock()

    # Mock setup_threads to actually add a mock thread we can check
    mock_thread = MagicMock()
    app._threads = [mock_thread]

    # Mock _setup_threads to do nothing (we set self._threads manually above)
    app._setup_threads = MagicMock()

    app.run()

    # Verify signal handlers registered
    assert mock_signal.called

    # Verify thread started
    mock_thread.start.assert_called_once()

    # Verify join called
    mock_thread.join.assert_called()
