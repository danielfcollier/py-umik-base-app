"""
Unit tests for BaseApp.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

from unittest.mock import ANY, MagicMock, patch

import pytest

from umik_base_app.core.base_app import BaseApp


@pytest.fixture
def mock_dependencies():
    """Return mocks for AppConfig and pipeline."""
    config = MagicMock()
    # FIX: Set a valid string for run_mode so OperationalMode enum conversion works
    config.run_mode = "monolithic"
    config.zmq_host = "127.0.0.1"
    config.zmq_port = 5555
    config.audio_device = MagicMock()
    config.sample_rate = 48000
    config.buffer_seconds = 1.0

    pipeline = MagicMock()
    return config, pipeline


@patch("umik_base_app.core.base_app.create_transport")
@patch("umik_base_app.core.base_app.ConsumerThread")
@patch("umik_base_app.core.base_app.ListenerThread")
def test_app_initialization_and_thread_setup(
    mock_listener_cls, mock_consumer_cls, mock_create_transport, mock_dependencies
):
    """
    Test that BaseApp initializes correctly and sets up the
    producer/consumer threads in its thread list.
    """
    app_config, pipeline = mock_dependencies

    # Instantiate the app
    app = BaseApp(app_config, pipeline)

    # Assert initial state
    assert app._config == app_config
    assert app._pipeline == pipeline
    assert len(app._threads) == 0

    # Trigger thread setup
    app._setup_threads()

    # Assert Transport was created
    mock_create_transport.assert_called_once()
    transport_instance = mock_create_transport.return_value

    # Assert Listener Thread Creation
    mock_listener_cls.assert_called_once_with(
        audio_device_config=ANY,
        transport=transport_instance,  # Verifies we passed the transport
        stop_event=app._stop_event,
    )

    # Assert Consumer Thread Creation
    mock_consumer_cls.assert_called_once_with(
        transport=transport_instance,  # Verifies we passed the transport
        stop_event=app._stop_event,
        pipeline=pipeline,
        consumer_queue_timeout_seconds=ANY,
    )

    # Assert Threads were added to the internal list
    assert len(app._threads) == 2
