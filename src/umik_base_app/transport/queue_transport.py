"""
Implements an in-memory transport layer using standard Python queues.

This module provides a thread-safe implementation of the AudioTransport interface
designed for monolithic application execution, where the producer (listener)
and consumer (pipeline) reside within the same process.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

import queue
from datetime import datetime

import numpy as np

from .base_transport import AudioTransport


class QueueInMemoryTransport(AudioTransport):
    """
    Wrapper around Python's threading.Queue for monolithic execution.

    This class facilitates the transfer of audio data between threads using a
    First-In-First-Out (FIFO) structure. It is the default transport mode
    when the application is not running in a distributed ZMQ configuration.
    """

    def __init__(self, max_size: int = 0):
        """
        Initializes the underlying thread-safe queue.

        :param max_size: The maximum number of items allowed in the queue.
                         An integer <= 0 means an infinite queue size.
        """
        self._queue = queue.Queue(maxsize=max_size)

    def send(self, data: tuple[np.ndarray, datetime]) -> None:
        """
        Pushes an audio data packet onto the queue.

        This method mimics 'put_nowait' behavior; if the queue has a max_size
        and is full, it will raise a queue.Full exception. This is intended
        to ensure the producer does not block and lag behind the real-time stream.

        :param data: A tuple containing the audio samples and capture timestamp.
        """
        # Mimic put_nowait behavior to maintain real-time performance
        self._queue.put_nowait(data)

    def recv(self, timeout_seconds: float) -> tuple[np.ndarray, datetime]:
        """
        Retrieves an audio data packet from the queue.

        :param timeout_seconds: Maximum time in seconds to block waiting for data.
        :return: A tuple containing the audio chunk and its timestamp.
        :raises queue.Empty: If no data is available within the timeout period.
        """
        return self._queue.get(timeout=timeout_seconds)

    def close(self):
        """
        Performs cleanup for the transport.

        For an in-memory queue, no explicit resource release (like closing sockets)
        is required as the Python Garbage Collector (GC) handles the queue object.
        """
        pass  # GC handles the queue
