"""
Integration tests for ZMQ Topology.
Spins up real ZMQ sockets on localhost to verify Producer-Consumer flow.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

import socket
import time
from datetime import datetime

import numpy as np
import pytest

from umik_base_app import ZmqConsumerTransport, ZmqProducerTransport


def get_free_port():
    """Finds a free port on localhost to avoid collisions during testing."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


@pytest.mark.integration
@pytest.mark.timeout(5)  # Fails test if it hangs > 5s (requires pytest-timeout)
def test_real_zmq_socket_transmission():
    """
    End-to-End test of the Transport Layer using real TCP sockets.
    1. Starts a Producer bound to a random port.
    2. Starts a Consumer connected to that port.
    3. Sends data and verifies it arrives intact.
    """
    port = get_free_port()
    host = "127.0.0.1"
    messages = 100

    # --- 1. Setup Topology ---
    producer = ZmqProducerTransport(port=port, host="*", messages=messages)
    consumer = ZmqConsumerTransport(host=host, port=port, messages=messages)

    # Allow ZMQ internal handshake (PUB/SUB "slow joiner" syndrome)
    time.sleep(0.2)

    # --- 2. Send Data ---
    test_chunk = np.random.rand(100).astype("float32")
    test_time = datetime.now()

    # Send a few frames. PUB/SUB is best-effort; the first msg might drop
    # if connection isn't 100% ready, so we send a burst.
    for _ in range(5):
        producer.send((test_chunk, test_time))
        time.sleep(0.01)

    # --- 3. Receive Data ---
    # We might receive any of the 5 sent chunks.
    # We just need to confirm we got *one* valid chunk matching our data.
    received_chunk, received_time = consumer.recv(timeout_seconds=2.0)

    # --- 4. Verify ---
    np.testing.assert_array_equal(received_chunk, test_chunk)
    assert received_time == test_time

    # --- 5. Cleanup ---
    producer.close()
    consumer.close()
