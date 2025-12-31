"""
Defines the transport layer for audio data exchange.

Allows switching between in-memory queues (monolithic app) and ZMQ sockets
(distributed app) transparently.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime

import numpy as np

from ..operational_model import OperationalMode
from ..settings import get_settings
from .queue_transport import QueueInMemoryTransport
from .zmq_transport import ZmqConsumerTransport, ZmqProducerTransport

logger = logging.getLogger(__name__)

settings = get_settings()


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


def create_transport(mode: str, zmq_host: str | None = None, zmq_port: int | None = None) -> AudioTransport:
    """
    Factory to create the correct transport instance based on the application mode.

    :param mode: The operational mode of the application.
                 - "monolithic": Standard producer-consumer in a single process via queues.
                 - "producer": Capture-only mode sending data via ZMQ PUB.
                 - "consumer": Processing-only mode receiving data via ZMQ SUB.
    :param zmq_host: (Optional) The IP address or hostname for ZMQ connections.
    :param zmq_port: (Optional) The TCP port for ZMQ communication.
    :return: An instance of a concrete AudioTransport implementation.
    :raises ValueError: If an unsupported mode is provided.
    """
    if OperationalMode.is_monolithic(mode):
        logger.debug("Creating in-memory queue transport.")
        return QueueInMemoryTransport()
    elif OperationalMode.is_producer(mode):
        logger.debug(f"Creating ZMQ producer transport on port {zmq_port}.")
        return ZmqProducerTransport(port=zmq_port)
    elif OperationalMode.is_consumer(mode):
        logger.debug(f"Creating ZMQ consumer transport connecting to {zmq_host}:{zmq_port}.")
        return ZmqConsumerTransport(host=zmq_host, port=zmq_port)
    else:
        raise ValueError(f"Unknown mode: {mode}")
