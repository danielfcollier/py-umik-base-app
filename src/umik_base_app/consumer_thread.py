"""
Implements the audio stream consumer thread.

This module contains the class responsible for fetching audio chunks from a
queue and dispatching them to the audio pipeline for processing and consumption.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

import logging
import queue
import threading

from .audio_pipeline import AudioPipeline
from .transports.base_transport import AudioTransport

logger = logging.getLogger(__name__)


class ConsumerThread:
    """
    A thread dedicated to processing audio chunks received from a queue.

    This class acts as the "Consumer" in a producer-consumer pattern. It continuously
    fetches audio data (packaged as a tuple of numpy array and timestamp) from a
    `queue.Queue` and delegates processing to the `AudioPipeline`.

    It runs until a `stop_event` is set, ensuring graceful shutdown. It includes
    robust error handling for queue operations and pipeline execution.
    """

    def __init__(
        self,
        transport: AudioTransport,
        stop_event: threading.Event,
        pipeline: AudioPipeline,
        consumer_queue_timeout_seconds: int,
    ):
        """
        Initializes the audio consumer thread.

        :param transport: The `AudioTransport` instance from which
                            audio data tuples (audio_chunk, timestamp) will be fetched.
        :param stop_event: A `threading.Event` object used to signal the thread
                           to terminate its loop and exit gracefully.
        :param pipeline: An instance of `AudioPipeline` configured with the
                         necessary processors and sinks to handle the audio data.
        :param consumer_queue_timeout_seconds: Timeout for blocking queue gets.
        """
        self._transport = transport
        self._stop_event = stop_event
        self._pipeline = pipeline
        self._consumer_queue_timeout_seconds = consumer_queue_timeout_seconds

        self._class_name = self.__class__.__name__
        logger.info(f"{self._class_name} initialized with pipeline.")

    def run(self):
        """
        The main execution loop for the audio consumer thread.

        Continuously attempts to retrieve audio data (chunk, timestamp) from the queue.
        If data is available, it passes it to the `AudioPipeline.execute()` method.

        Includes timeouts for queue retrieval to remain responsive to the stop signal
        and error handling for execution failures.
        """
        logger.info(f"{self._class_name} thread started.")

        while not self._stop_event.is_set():
            try:
                # Retrieve the tuple (audio_chunk, timestamp) from the queue
                audio_chunk, timestamp = self._transport.recv(timeout_seconds=self._consumer_queue_timeout_seconds)

                if self._stop_event.is_set():
                    logger.debug("Stop event detected. Discarding remaining queue items.")
                    break

                # Execute the pipeline for this chunk
                try:
                    self._pipeline.execute(audio_chunk, timestamp)
                except Exception as e:
                    logger.error(f"Error executing pipeline: {e}", exc_info=True)

            except queue.Empty:
                logger.debug("Queue empty, continuing.")
                continue
            except Exception as e:
                logger.error(
                    f"Unexpected error in {self._class_name} run loop: {e}",
                    exc_info=True,
                )
                self._stop_event.set()

        logger.info(f"{self._class_name} thread finished.")
