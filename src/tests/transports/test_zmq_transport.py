"""
Unit tests for Transport Layer.
Mocks ZMQ to verify serialization and logic without networking.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

import queue
from unittest.mock import MagicMock, patch, sentinel

import pytest
import zmq

from umik_base_app.settings import get_settings
from umik_base_app.transports.zmq_transport import (
    ZmqConsumerTransport,
    ZmqProducerTransport,
)

settings = get_settings()


@patch("zmq.Context")
def test_zmq_producer_initialization(mock_context):
    """Test that Producer binds to the correct address."""
    mock_socket = MagicMock()
    mock_context.return_value.socket.return_value = mock_socket

    transport = ZmqProducerTransport(port=5555, host="0.0.0.0", messages=100)

    mock_socket.bind.assert_called_with("tcp://0.0.0.0:5555")
    assert transport.socket == mock_socket


@patch("umik_base_app.transports.zmq_transport.pickle")
@patch("zmq.Context")
def test_zmq_producer_send_serialization(mock_context, mock_pickle):
    """Test that data is pickled before sending."""
    mock_socket = MagicMock()
    mock_context.return_value.socket.return_value = mock_socket

    # Configure mock pickle to return a sentinel byte string
    mock_pickle.dumps.return_value = sentinel.pickled_bytes

    transport = ZmqProducerTransport(host="*", port=5555, messages=100)

    # FIX: Pass a tuple (chunk, timestamp) because send() unpacks it
    transport.send((sentinel.chunk, sentinel.timestamp))

    # Verify pickle was called with the tuple
    mock_pickle.dumps.assert_called_once_with((sentinel.chunk, sentinel.timestamp))

    # Verify socket.send was called with the result of pickle.dumps
    mock_socket.send.assert_called_once_with(sentinel.pickled_bytes)


@patch("zmq.Context")
def test_zmq_consumer_initialization(mock_context):
    """Test that Consumer connects to the correct address."""
    mock_socket = MagicMock()
    mock_context.return_value.socket.return_value = mock_socket

    # FIX: Added required 'messages' argument
    ZmqConsumerTransport(host="127.0.0.1", port=5555, messages=100)

    mock_socket.connect.assert_called_with("tcp://127.0.0.1:5555")
    # Verify RCVHWM is set
    mock_socket.setsockopt.assert_any_call(zmq.RCVHWM, 100)


@patch("zmq.Context")
def test_zmq_consumer_recv_timeout(mock_context):
    """Test that Consumer raises queue.Empty if poll returns 0."""
    mock_socket = MagicMock()
    mock_context.return_value.socket.return_value = mock_socket

    transport = ZmqConsumerTransport(host="localhost", port=5555, messages=100)

    # Simulate poll returning 0 (no data)
    mock_socket.poll.return_value = 0

    with pytest.raises(queue.Empty):
        transport.recv(timeout_seconds=0.1)


@patch("umik_base_app.transports.zmq_transport.pickle")
@patch("zmq.Context")
def test_zmq_consumer_recv_success(mock_context, mock_pickle):
    """Test that Consumer correctly unpickles received data."""
    mock_socket = MagicMock()
    mock_context.return_value.socket.return_value = mock_socket

    transport = ZmqConsumerTransport(host="localhost", port=5555, messages=100)

    # 1. Poll returns success
    mock_socket.poll.return_value = 1

    # 2. Recv returns specific sentinel bytes
    mock_socket.recv.return_value = sentinel.raw_bytes

    # 3. Pickle loads returns sentinel data object
    mock_pickle.loads.return_value = sentinel.unpickled_data

    received_data = transport.recv(timeout_seconds=0.1)

    # Verify flow
    mock_socket.recv.assert_called_once()
    mock_pickle.loads.assert_called_once_with(sentinel.raw_bytes)
    assert received_data is sentinel.unpickled_data
