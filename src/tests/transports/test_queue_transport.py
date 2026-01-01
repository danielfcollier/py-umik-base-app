"""
Unit tests for Transport Layer.
Mocks ZMQ to verify logic without networking.
"""

import queue
from unittest.mock import sentinel

import pytest

from umik_base_app import QueueInMemoryTransport


def test_memory_transport_fifo():
    transport = QueueInMemoryTransport()

    # Send a sentinel object
    transport.send(sentinel.payload)

    # Verify we receive the exact same object instance
    received = transport.recv(timeout_seconds=0.1)

    assert received is sentinel.payload


def test_memory_transport_timeout():
    transport = QueueInMemoryTransport()
    with pytest.raises(queue.Empty):
        transport.recv(timeout_seconds=0.01)
