"""
Unit tests for Transport Layer.
Mocks ZMQ to verify logic without networking.
"""

import queue
from datetime import datetime

import numpy as np
import pytest

from umik_base_app.transports.queue_transport import QueueInMemoryTransport


# --- InMemory Tests ---
def test_memory_transport_fifo():
    transport = QueueInMemoryTransport()
    data = (np.zeros(10), datetime.now())

    transport.send(data)
    received = transport.recv(timeout_seconds=0.1)

    assert received == data


def test_memory_transport_timeout():
    transport = QueueInMemoryTransport()
    with pytest.raises(queue.Empty):
        transport.recv(timeout_seconds=0.01)
