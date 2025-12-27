"""
Defines the base application class for audio monitoring tasks.

This module provides an abstract layer (BaseApp) built upon ThreadApp,
specifically tailored for applications that involve audio input streams,
pipeline processing, and configuration handling.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

import logging
import threading

from ..hardware.config import HardwareConfig
from .consumer_thread import ConsumerThread
from .listener_thread import ListenerThread
from .pipeline import AudioPipeline
from .thread_app import ThreadApp

logger = logging.getLogger(__name__)

CONSUMER_QUEUE_TIMEOUT_SECONDS = 1


class BaseApp(ThreadApp):
    """
    Abstract base class for audio processing applications.

    Extends ThreadApp to specifically set up an audio listener (producer)
    thread and an audio consumer thread based on provided configuration and
    processing pipeline.
    """

    def __init__(self, audio_config: HardwareConfig, pipeline: AudioPipeline):
        """
        Initializes the BaseApp, setting up configuration and threads.

        :param audio_config: An instance of HardwareConfig containing validated
                             settings for the audio device and stream (sample rate,
                             buffer size, device ID, etc.).
        :param pipeline:     An instance of AudioPipeline configured with the
                             necessary processors (e.g., HardwareCalibrator) and sinks
                             (e.g., Recorder, Metrics).
        """
        # Initialize the parent ThreadApp (creates queue, lock, stop_event, thread list).
        super().__init__()
        logger.debug("BaseApp initializing...")

        # Store the essential configuration and the processing pipeline.
        self._audio_config: HardwareConfig = audio_config
        self._pipeline: AudioPipeline = pipeline

    def _setup_threads(self):
        """
        Implementation of the abstract method from ThreadApp.
        Creates and registers the standard Audio Listener and Consumer threads,
        wrapping them in the error guard to ensure app shutdown on failure.
        """
        logger.info("Setting up audio listener and consumer threads...")

        # --- Create Listener Thread (The "Ear") ---
        # Instantiates the ListenerThread, which captures raw audio from the hardware device.
        # It pushes data to self._queue and monitors self._stop_event to ensure
        # it releases hardware resources and exits the recording loop cleanly on shutdown.
        listener = ListenerThread(
            audio_device_config=self._audio_config,
            audio_queue=self._queue,
            stop_event=self._stop_event,
        )

        listener_thread = threading.Thread(
            target=self._thread_guard(listener.run),
            name="ListenerThread",
        )
        self._threads.append(listener_thread)

        # --- Create Consumer Thread (The "Brain") ---
        # Instantiates the ConsumerThread, which retrieves audio from self._queue.
        # It passes data through the pipeline (executing components like the HardwareCalibrator).
        # The consumer_queue_timeout_seconds prevents blocking forever on an empty queue,
        # allowing the thread to periodically check self._stop_event and shut down gracefully.
        consumer = ConsumerThread(
            audio_queue=self._queue,
            stop_event=self._stop_event,
            pipeline=self._pipeline,
            consumer_queue_timeout_seconds=CONSUMER_QUEUE_TIMEOUT_SECONDS,
        )

        consumer_thread = threading.Thread(
            target=self._thread_guard(consumer.run),
            name="ConsumerThread",
        )
        self._threads.append(consumer_thread)

        logger.info(f"Registered {len(self._threads)} standard audio threads.")
