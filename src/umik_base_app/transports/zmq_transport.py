"""
Implements ZeroMQ-based transport for distributed audio monitoring.

This module provides concrete implementations of the AudioTransport interface using
ZeroMQ (ZMQ) sockets, allowing audio data to be streamed across a network between
producers (capture devices) and consumers (processing/recording units).

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

import logging
import pickle
import queue
from datetime import datetime

import numpy as np
import zmq

from .base_transport import AudioTransport

logger = logging.getLogger(__name__)


class ZmqProducerTransport(AudioTransport):
    """
    Sends audio data via a ZMQ PUB (Publisher) socket.

    This class acts as the 'Producer' side of the transport, typically running
    on edge hardware like a Raspberry Pi to broadcast captured audio chunks
    over the network.
    """

    def __init__(self, host: str, port: int, messages: int):
        """
        Initializes the ZMQ Publisher socket.

        :param port: The TCP port to bind to for outgoing data.
        :param host: The network interface to bind to. Defaults to "*" (all interfaces).
        """
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.PUB)

        # SNDHWM (Send High Water Mark): Sets a limit on how many messages are
        # queued in memory before the socket starts dropping or blocking.
        # A value of 100 provides a safety buffer for transient network jitter.
        self.socket.setsockopt(zmq.SNDHWM, messages)

        address = f"tcp://{host}:{port}"
        self.socket.bind(address)
        logger.info(f"ZMQ Publisher bound to {address}")

    def send(self, data: tuple[np.ndarray, datetime]) -> None:
        """
        Serializes and broadcasts an audio chunk and its timestamp.

        :param data: A tuple containing the audio samples (np.ndarray) and
                     capture timestamp (datetime).
        """
        audio_chunk, timestamp = data

        # Serialize the tuple using pickle for easy Python-to-Python transfer.
        # Note: If interoperability with other languages is required,
        # consider using flatbuffers, protobuf, or raw bytes + JSON headers.
        payload = pickle.dumps((audio_chunk, timestamp))
        self.socket.send(payload)

    def recv(self, timeout_seconds: float):
        """
        The Publisher socket is send-only.

        :raises NotImplementedError: Always, as Producers do not receive data.
        """
        raise NotImplementedError("Producer cannot receive.")

    def close(self):
        """
        Gracefully shuts down the ZMQ socket and context.
        """
        self.socket.close()
        self.context.term()
        logger.debug("ZmqProducerTransport closed.")


class ZmqConsumerTransport(AudioTransport):
    """
    Receives audio data via a ZMQ SUB (Subscriber) socket.

    This class acts as the 'Consumer' side of the transport, typically running
    on a workstation or server to collect data broadcast by edge producers.
    """

    def __init__(self, host: str, port: int, messages: int):
        """
        Initializes the ZMQ Subscriber socket and connects to a host.

        :param host: The IP address or hostname of the producer.
        :param port: The TCP port to connect to.
        """
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.SUB)

        # Subscribe to all incoming messages (empty prefix).
        self.socket.setsockopt(zmq.SUBSCRIBE, b"")

        # RCVHWM (Receive High Water Mark): Prevents memory exhaustion if the
        # consumer pipeline processing is slower than the incoming data rate.
        self.socket.setsockopt(zmq.RCVHWM, messages)

        address = f"tcp://{host}:{port}"
        self.socket.connect(address)
        logger.info(f"ZMQ Subscriber connected to {address}")

    def send(self, data):
        """
        The Subscriber socket is receive-only.

        :raises NotImplementedError: Always, as Consumers do not send data.
        """
        raise NotImplementedError("Consumer cannot send.")

    def recv(self, timeout_seconds: float) -> tuple[np.ndarray, datetime]:
        """
        Polls the socket for incoming audio data within a specific timeout.

        :param timeout_seconds: Maximum time in seconds to wait for data.
        :return: A tuple of (audio_chunk, timestamp).
        :raises queue.Empty: If no data is received before the timeout expires.
        """
        # Convert seconds to milliseconds for the ZMQ poll method
        timeout_milliseconds = int(timeout_seconds * 1000)

        # Poll to check if data is available without blocking the entire thread indefinitely
        if self.socket.poll(timeout_milliseconds) == 0:
            raise queue.Empty

        payload = self.socket.recv()
        return pickle.loads(payload)

    def close(self):
        """
        Gracefully shuts down the ZMQ socket and context.
        """
        self.socket.close()
        self.context.term()
        logger.debug("ZmqConsumerTransport closed.")
