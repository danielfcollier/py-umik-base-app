"""
Defines the base application class for audio monitoring tasks.

This module provides an abstract layer (BaseAudioApp) built upon BaseThreadApp,
specifically tailored for applications that involve audio input streams,
pipeline processing, and configuration handling.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

import logging
import threading

from src import (
    AudioDeviceConfig,
    AudioStreamsConsumerThread,
    AudioStreamsListenerThread,
)
from src.library.audio_pipeline import AudioPipeline
from src.library.base_thread_app import BaseThreadApp

logger = logging.getLogger(__name__)

CONSUMER_QUEUE_TIMEOUT_SECONDS = 1


class BaseAudioApp(BaseThreadApp):
    """
    Abstract base class for audio processing applications.

    Extends BaseThreadApp to specifically set up an audio listener (producer)
    thread and an audio consumer thread based on provided configuration and
    processing pipeline.
    """

    def __init__(self, audio_config: AudioDeviceConfig, pipeline: AudioPipeline):
        """
        Initializes the BaseAudioApp, setting up configuration and threads.

        :param audio_config: An instance of AudioDeviceConfig containing validated
                             settings for the audio device and stream (sample rate,
                             buffer size, device ID, etc.).
        :param pipeline:     An instance of AudioPipeline configured with the
                             necessary processors (e.g., Calibrator) and sinks
                             (e.g., Recorder, Metrics).
        """
        # Initialize the parent BaseThreadApp (creates queue, lock, stop_event, thread list).
        super().__init__()
        logger.debug("BaseAudioApp initializing...")

        # Store the essential configuration and the processing pipeline.
        self._audio_config: AudioDeviceConfig = audio_config
        self._pipeline: AudioPipeline = pipeline

    def _setup_threads(self):
        """
        Implementation of the abstract method from BaseThreadApp.
        Creates and registers the standard Audio Listener and Consumer threads,
        wrapping them in the error guard to ensure app shutdown on failure.
        """
        logger.info("Setting up audio listener and consumer threads...")

        # --- Create Listener Thread ---
        # Responsible for reading audio from the hardware device configured in
        # self._audio_config and putting (audio_chunk, timestamp) tuples onto self._queue.
        listener = AudioStreamsListenerThread(
            audio_device_config=self._audio_config,
            audio_queue=self._queue,
            stop_event=self._stop_event,
        )

        listener_thread = threading.Thread(
            target=self._thread_guard(listener.run),  # Wrap in guard!
            name="AudioListenerThread",
        )
        self._threads.append(listener_thread)

        # --- Create Consumer Thread ---
        # Responsible for getting (audio_chunk, timestamp) tuples from self._queue
        # and delegating processing to the self._pipeline.
        consumer = AudioStreamsConsumerThread(
            audio_queue=self._queue,
            stop_event=self._stop_event,
            pipeline=self._pipeline,
            consumer_queue_timeout_seconds=CONSUMER_QUEUE_TIMEOUT_SECONDS,
        )

        consumer_thread = threading.Thread(
            target=self._thread_guard(consumer.run),  # Wrap in guard!
            name="AudioConsumerThread",
        )
        self._threads.append(consumer_thread)

        logger.info(f"Registered {len(self._threads)} standard audio threads.")
