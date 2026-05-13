"""
Unit tests for AudioBaseApp.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

from unittest.mock import ANY, MagicMock, patch, sentinel

import pytest

from umik_base_app import AudioBaseApp, OperationalMode


@pytest.fixture
def mock_config():
    """Return a mock AppConfig."""
    config = MagicMock()
    config.run_mode = OperationalMode.MONOLITHIC
    config.zmq_host = sentinel.zmq_host
    config.zmq_port = sentinel.zmq_port
    config.audio_device = MagicMock()
    config.audio_device.id = sentinel.device_id
    config.audio_device.name = sentinel.device_name
    config.sample_rate = sentinel.sample_rate
    config.buffer_seconds = sentinel.buffer_seconds
    return config


@patch("umik_base_app.audio_base_app.HardwareConfig")
@patch("umik_base_app.audio_base_app.ConsumerThread")
@patch("umik_base_app.audio_base_app.ListenerThread")
def test_app_initialization_and_thread_setup(
    mock_listener_cls,
    mock_consumer_cls,
    mock_hardware_config_cls,
    mock_config,
    mock_transport,
):
    """
    Test that AudioBaseApp initializes correctly and sets up the
    producer/consumer threads in its thread list.
    """
    # Act - inject transport directly
    app = AudioBaseApp(mock_config, sentinel.pipeline, transport=mock_transport)

    # Assert initial state
    assert app._config == mock_config
    assert app._pipeline == sentinel.pipeline
    assert app._transport == mock_transport
    assert len(app._threads) == 0

    # Act - setup threads
    app._setup_threads()

    # Assert thread setup
    mock_hardware_config_cls.assert_called_once_with(
        target_audio_device=mock_config.audio_device,
        sample_rate=sentinel.sample_rate,
        buffer_seconds=sentinel.buffer_seconds,
    )

    mock_listener_cls.assert_called_once_with(
        audio_device_config=mock_hardware_config_cls.return_value,
        transport=mock_transport,
        stop_event=app._stop_event,
    )

    mock_consumer_cls.assert_called_once_with(
        transport=mock_transport,
        stop_event=app._stop_event,
        pipeline=sentinel.pipeline,
        consumer_queue_timeout_seconds=ANY,
    )

    assert len(app._threads) == 2


@patch("umik_base_app.audio_base_app.create_transport")
def test_app_creates_transport_when_not_injected(
    mock_create_transport,
    mock_config,
):
    """Test that AudioBaseApp creates transport when none is injected."""
    mock_create_transport.return_value = sentinel.created_transport

    app = AudioBaseApp(mock_config, sentinel.pipeline)

    mock_create_transport.assert_called_once_with(
        mode=OperationalMode.MONOLITHIC,
        zmq_host=sentinel.zmq_host,
        zmq_port=sentinel.zmq_port,
    )
    assert app._transport == sentinel.created_transport
