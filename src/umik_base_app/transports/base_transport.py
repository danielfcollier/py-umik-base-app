"""
Defines the transport layer for audio data exchange.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime

import numpy as np

logger = logging.getLogger(__name__)


class AudioTransport(ABC):
    """
    Abstract base class for audio data transport.

    This interface defines the contract for sending and receiving audio data
    packets (consisting of a numpy array and a timestamp) regardless of the
    underlying communication mechanism (e.g., in-memory queues or network sockets).
    """

    @abstractmethod
    def send(self, data: tuple[np.ndarray, datetime]) -> None:
        """
        Send an audio chunk and its associated timestamp.

        :param data: A tuple containing the (np.ndarray) audio samples and
                     the (datetime) capture timestamp.
        """
        pass

    @abstractmethod
    def recv(self, timeout_seconds: float) -> tuple[np.ndarray, datetime]:
        """
        Receive an audio chunk and its associated timestamp.

        :param timeout_seconds: Maximum time to wait for data before raising an exception.
        :return: A tuple containing the audio chunk and timestamp.
        :raises queue.Empty: If no data is available within the timeout period.
        """
        pass

    @abstractmethod
    def close(self):
        """
        Clean up transport resources.

        This should be called during application shutdown to ensure sockets,
        queues, or contexts are closed gracefully.
        """
        pass
