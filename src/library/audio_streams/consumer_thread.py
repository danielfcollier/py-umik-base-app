"""
Implements the audio stream consumer thread.

This module contains the class responsible for fetching audio chunks from a
shared queue and dispatching them to registered callback functions for
processing (e.g., analysis, recording, metrics calculation).

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

import queue
import threading
import logging

from src import AudioProcessingCallback

logger = logging.getLogger(__name__)


class AudioStreamsConsumerThread:
    """
    A thread dedicated to processing audio chunks received from a shared queue.

    This class acts as the "Consumer" in a producer-consumer pattern. It continuously
    fetches audio data (packaged as a tuple of numpy array and timestamp) from a
    `queue.Queue` and passes it to a list of registered callback functions for
    processing (e.g., calculating metrics, running ML models, managing recordings).

    It runs until a `stop_event` is set, ensuring graceful shutdown. It includes
    robust error handling for queue operations and callback execution.
    """

    def __init__(
        self,
        shared_audio_queue: queue.Queue,
        stop_event: threading.Event,
        callbacks: list[AudioProcessingCallback],
        consumer_queue_timeout_seconds: int,
    ):
        """
        Initializes the audio consumer thread.

        :param shared_audio_queue: The thread-safe `queue.Queue` instance from which
                                   audio data tuples (audio_chunk, timestamp) will be fetched.
        :param stop_event: A `threading.Event` object used to signal the thread
                           to terminate its loop and exit gracefully.
        :param callbacks: A list of functions (or methods) that will be called for each
                          audio chunk. Each function must accept two arguments:
                          `audio_chunk (np.ndarray)` and `timestamp (datetime)`.
        """
        self._queue = shared_audio_queue
        self._stop_event = stop_event
        self._callbacks = callbacks if callbacks else []
        self._consumer_queue_timeout_seconds = consumer_queue_timeout_seconds
        if not self._callbacks:
            logger.warning("AudioStreamsConsumerThread initialized with no callback functions.")

        self._class_name = self.__class__.__name__
        logger.info(f"{self._class_name} initialized with {len(self._callbacks)} callbacks.")

    def run(self):
        """
        The main execution loop for the audio consumer thread.

        Continuously attempts to retrieve audio data (chunk, timestamp) from the queue.
        If data is available, it iterates through the registered callback functions,
        calling each one with the audio chunk and timestamp.

        Includes timeouts for queue retrieval to remain responsive to the stop signal
        and error handling for individual callback failures.
        """
        logger.info(f"{self._class_name} thread started.")

        while not self._stop_event.is_set():
            try:
                audio_chunk, timestamp = self._queue.get(timeout=self._consumer_queue_timeout_seconds)
                for callback in self._callbacks:
                    try:
                        callback(audio_chunk, timestamp)
                    except Exception as e:
                        logger.error(f"Error executing callback {callback.__name__}: {e}", exc_info=True)

            except queue.Empty:
                logger.debug("Queue empty, continuing.")
                continue
            except Exception as e:
                logger.error(f"Unexpected error in {self._class_name} run loop: {e}", exc_info=True)
                self._stop_event.set()

        logger.info(f"{self._class_name} thread finished.")
