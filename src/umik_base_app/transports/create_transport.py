"""
Allows switching between in-memory queues (monolithic app) and ZMQ sockets
(distributed app) transparently.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

import logging

from ..operational_mode import OperationalMode
from .base_transport import AudioTransport
from .queue_transport import QueueInMemoryTransport
from .zmq_transport import ZmqConsumerTransport, ZmqProducerTransport

logger = logging.getLogger(__name__)


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
