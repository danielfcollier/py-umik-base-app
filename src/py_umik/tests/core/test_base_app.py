"""
Unit tests for BaseApp.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

from unittest.mock import MagicMock, patch

import pytest

from py_umik.core.base_app import BaseApp


@pytest.fixture
def mock_dependencies():
    """Return mocks for config and pipeline."""
    config = MagicMock()
    pipeline = MagicMock()
    return config, pipeline


@patch("py_umik.core.base_app.ConsumerThread")
@patch("py_umik.core.base_app.ListenerThread")
def test_app_initialization_and_thread_setup(mock_listener_cls, mock_consumer_cls, mock_dependencies):
    """
    Test that BaseApp initializes correctly and sets up the
    producer/consumer threads in its thread list.
    """
    audio_config, pipeline = mock_dependencies

    # Instantiate the app
    app = BaseApp(audio_config, pipeline)

    # Assert initial state
    assert app._audio_config == audio_config
    assert app._pipeline == pipeline
    assert len(app._threads) == 0  # Threads not setup until requested

    # Trigger thread setup (normally called by ThreadApp.run/start,
    # but we call the protected method directly for unit testing)
    app._setup_threads()

    # Assert Listener Thread Creation
    mock_listener_cls.assert_called_once_with(
        audio_device_config=audio_config,
        audio_queue=app._queue,
        stop_event=app._stop_event,
    )

    # Assert Consumer Thread Creation
    mock_consumer_cls.assert_called_once_with(
        audio_queue=app._queue,
        stop_event=app._stop_event,
        pipeline=pipeline,
        consumer_queue_timeout_seconds=1,
    )

    # Assert Threads were added to the internal list
    # We expect 2 threads: Listener and Consumer
    assert len(app._threads) == 2
    assert app._threads[0].name == "ListenerThread"
    assert app._threads[1].name == "ConsumerThread"
