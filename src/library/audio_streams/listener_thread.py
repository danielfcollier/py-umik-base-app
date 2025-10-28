"""
Implements the audio stream listener (producer) thread.

This module contains the class responsible for opening an audio input stream,
continuously reading audio chunks from the microphone, and placing them onto
a queue for consumption by other threads.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

import queue
import threading
import sounddevice as sd
import logging

from src.library.audio_device.config import AudioDeviceConfig
from src.datetime_stamp import DatetimeStamp

logger = logging.getLogger(__name__)


class AudioStreamsListenerThread:
    """
    A thread dedicated to capturing audio from a specified input device.

    This class acts as the "Producer" in a producer-consumer pattern. Its sole
    responsibility is to continuously read audio chunks from the sound device
    using `sounddevice.InputStream` and place them onto a queue for further
    processing by other threads (Consumers).

    It runs until a `stop_event` is set, ensuring graceful shutdown.
    """

    def __init__(self, audio_device_config: AudioDeviceConfig, audio_queue: queue.Queue, stop_event: threading.Event):
        """
        Initializes the audio listener thread.

        :param audio_device_config: An object containing the configuration for the
                                    audio stream (e.g., sample rate, block size,
                                    device ID, dtype). This configuration dictates how
                                    the audio stream will be opened.
        :param audio_queue: A thread-safe `queue.Queue` instance. Raw audio chunks
                                    captured from the microphone will be put onto this queue.
        :param stop_event: A `threading.Event` object used to signal the thread
                           to terminate its loop and exit gracefully. This event
                           is typically set by the main application thread upon
                           receiving a shutdown signal (SIGINT/SIGTERM).
        """
        self._audio_device_config = audio_device_config
        self._queue = audio_queue
        self._stop_event = stop_event

        self._class_name = self.__class__.__name__
        logger.info(f"{self._class_name} initialized.")

    def run(self):
        """
        The main execution loop for the audio listener thread.

        Continuously reads audio chunks from the configured input device via
        `sounddevice.InputStream` and puts them onto the queue as tuples containing
        the audio data (numpy array) and a timestamp.

        It runs until the `stop_event` is set.
        """
        logger.info(f"{self._class_name} thread started.")

        try:
            device_id = self._audio_device_config.id
            sample_rate = self._audio_device_config.sample_rate
            dtype = self._audio_device_config.dtype
            block_size = self._audio_device_config.block_size

            with sd.InputStream(
                device=device_id,
                blocksize=block_size,
                samplerate=sample_rate,
                dtype=dtype,
                channels=1,
            ) as stream:
                logger.debug(
                    f"Opened audio stream on device ID {device_id} with SR={sample_rate}, Blocksize={block_size}."
                )

                while not self._stop_event.is_set():
                    audio_chunk, overflowed = stream.read(block_size)

                    if overflowed:
                        logger.warning("Audio buffer overflowed! System might be overloaded.")

                    timestamp = DatetimeStamp.get()
                    audio_data = (audio_chunk, timestamp)
                    self._queue.put(audio_data)

                    logger.debug(f"Sent audio chunk (shape: {audio_chunk.shape}) with timestamp {timestamp} to queue.")

        except sd.PortAudioError as pa_err:
            logger.error(f"PortAudioError in audio stream: {pa_err}", exc_info=True)
            self._stop_event.set()
        except Exception as e:
            logger.error(f"Unexpected error in audio listener thread: {e}", exc_info=True)
            self._stop_event.set()
        finally:
            logger.info(f"{self._class_name} thread finished.")
