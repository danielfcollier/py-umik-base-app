"""
Unit tests for Transport Layer.
Mocks ZMQ to verify serialization and logic without networking.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

import pickle
import queue
from datetime import datetime
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import zmq

from umik_base_app.settings import get_settings
from umik_base_app.transport.queue_transport import QueueInMemoryTransport
from umik_base_app.transport.zmq_transport import (
    ZmqConsumerTransport,
    ZmqProducerTransport,
)

settings = get_settings()


# --- InMemory Transport Tests ---
def test_memory_transport_fifo():
    """Test standard First-In-First-Out behavior of memory transport."""
    transport = QueueInMemoryTransport()
    data_1 = (np.array([1]), datetime.now())
    data_2 = (np.array([2]), datetime.now())

    transport.send(data_1)
    transport.send(data_2)

    assert transport.recv(timeout_seconds=0.1) == data_1
    assert transport.recv(timeout_seconds=0.1) == data_2


def test_memory_transport_timeout():
    """Test that recv raises Empty on timeout."""
    transport = QueueInMemoryTransport()
    with pytest.raises(queue.Empty):
        transport.recv(timeout_seconds=0.01)


# --- ZMQ Producer Tests ---
@patch("zmq.Context")
def test_zmq_producer_initialization(mock_context):
    """Test that Producer binds to the correct address."""
    mock_socket = MagicMock()
    mock_context.return_value.socket.return_value = mock_socket

    transport = ZmqProducerTransport(port=5555, host="0.0.0.0")

    mock_socket.bind.assert_called_with("tcp://0.0.0.0:5555")
    assert transport.socket == mock_socket


@patch("zmq.Context")
def test_zmq_producer_send_serialization(mock_context):
    """Test that data is pickled before sending."""
    mock_socket = MagicMock()
    mock_context.return_value.socket.return_value = mock_socket

    transport = ZmqProducerTransport(port=5555)

    # Data to send
    audio_chunk = np.array([1, 2, 3])
    timestamp = datetime.now()
    data = (audio_chunk, timestamp)

    transport.send(data)

    # Verify socket.send was called with bytes
    mock_socket.send.assert_called_once()
    sent_payload = mock_socket.send.call_args[0][0]

    # Verify we can unpickle it back to original data
    unpickled = pickle.loads(sent_payload)
    np.testing.assert_array_equal(unpickled[0], audio_chunk)
    assert unpickled[1] == timestamp


# --- ZMQ Consumer Tests ---
@patch("zmq.Context")
def test_zmq_consumer_initialization(mock_context):
    """Test that Consumer connects to the correct address."""
    mock_socket = MagicMock()
    mock_context.return_value.socket.return_value = mock_socket

    ZmqConsumerTransport(host="127.0.0.1", port=5555)

    mock_socket.connect.assert_called_with("tcp://127.0.0.1:5555")
    mock_socket.setsockopt.assert_any_call(
        zmq.RCVHWM, settings.ZMQ.MESSAGES or 100
    )  # zmq.LINGER check implies cleanup safety


@patch("zmq.Context")
def test_zmq_consumer_recv_timeout(mock_context):
    """Test that Consumer raises queue.Empty if poll returns 0."""
    mock_socket = MagicMock()
    mock_context.return_value.socket.return_value = mock_socket

    transport = ZmqConsumerTransport(host="localhost", port=5555)

    # Simulate poll returning 0 (no data)
    mock_socket.poll.return_value = 0

    with pytest.raises(queue.Empty):
        transport.recv(timeout_seconds=0.1)


@patch("zmq.Context")
def test_zmq_consumer_recv_success(mock_context):
    """Test that Consumer correctly unpickles received data."""
    mock_socket = MagicMock()
    mock_context.return_value.socket.return_value = mock_socket

    transport = ZmqConsumerTransport(host="localhost", port=5555)

    # 1. Poll returns success
    mock_socket.poll.return_value = 1

    # 2. Recv returns pickled data
    original_data = (np.array([10, 20]), datetime.now())
    mock_socket.recv.return_value = pickle.dumps(original_data)

    received_data = transport.recv(timeout_seconds=0.1)

    np.testing.assert_array_equal(received_data[0], original_data[0])
    assert received_data[1] == original_data[1]
