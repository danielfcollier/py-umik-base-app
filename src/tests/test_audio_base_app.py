"""
Unit tests for AudioBaseApp.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

from unittest.mock import ANY, MagicMock, patch, sentinel

import pytest

from umik_base_app import AudioBaseApp


@pytest.fixture
def mock_dependencies():
    """Return mocks for AppConfig and pipeline."""
    config = MagicMock()

    config.run_mode = "monolithic"

    config.zmq_host = sentinel.zmq_host
    config.zmq_port = sentinel.zmq_port

    config.audio_device = MagicMock()
    config.audio_device.id = sentinel.device_id
    config.audio_device.name = sentinel.device_name

    config.sample_rate = sentinel.sample_rate
    config.buffer_seconds = sentinel.buffer_seconds

    pipeline = sentinel.pipeline
    return config, pipeline


@patch("umik_base_app.audio_base_app.settings")
@patch("umik_base_app.audio_base_app.HardwareConfig")
@patch("umik_base_app.audio_base_app.create_transport")
@patch("umik_base_app.audio_base_app.ConsumerThread")
@patch("umik_base_app.audio_base_app.ListenerThread")
def test_app_initialization_and_thread_setup(
    mock_listener_cls,
    mock_consumer_cls,
    mock_create_transport,
    mock_hardware_config_cls,
    mock_settings,
    mock_dependencies,
):
    """
    Test that AudioBaseApp initializes correctly and sets up the
    producer/consumer threads in its thread list.
    """
    # Prepare
    app_config, pipeline = mock_dependencies

    mock_create_transport.return_value = sentinel.transport
    mock_settings.AUDIO.HIGH_PRIORITY = sentinel.high_priority

    # Instantiate the app
    app = AudioBaseApp(app_config, pipeline)

    # Assert initial state
    assert app._config == app_config
    assert app._pipeline == sentinel.pipeline
    assert len(app._threads) == 0

    # Act
    app._setup_threads()

    # Assert calls
    mock_create_transport.assert_called_once_with(
        mode="monolithic", zmq_host=sentinel.zmq_host, zmq_port=sentinel.zmq_port
    )

    mock_hardware_config_cls.assert_called_once_with(
        target_audio_device=app_config.audio_device,
        sample_rate=sentinel.sample_rate,
        buffer_seconds=sentinel.buffer_seconds,
        high_priority=sentinel.high_priority,
    )

    mock_listener_cls.assert_called_once_with(
        audio_device_config=mock_hardware_config_cls.return_value,
        transport=sentinel.transport,
        stop_event=app._stop_event,
    )

    mock_consumer_cls.assert_called_once_with(
        transport=sentinel.transport,
        stop_event=app._stop_event,
        pipeline=sentinel.pipeline,
        consumer_queue_timeout_seconds=ANY,
    )

    # Assert Threads were added to the internal list
    assert len(app._threads) == 2
