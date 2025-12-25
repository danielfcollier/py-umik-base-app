"""
Implements the audio stream listener (producer) thread with robust error handling.

This module captures raw audio from the configured input device. It features:
1. A "Watchdog" reconnection loop to recover from USB device disconnects.
2. Non-blocking queue insertion to drop frames gracefully if the consumer lags.
3. Overflow detection to log hardware buffer issues.
4. A maximum retry limit to prevent infinite loops on permanent hardware failures.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

import logging
import queue
import threading

import sounddevice as sd

from ..hardware.config import HardwareConfig
from .datetime_stamp import DatetimeStamp

logger = logging.getLogger(__name__)

RECONNECT_DELAY_SECONDS = 5
RECONNECT_MAX_RETRIES = 10


class ListenerThread:
    """
    A thread dedicated to capturing audio from a specified input device.

    his class acts as the "Producer" in a producer-consumer pattern.  It runs
    a continuous loop that attempts to maintain an active audio stream. If
    the hardware fails (e.g., USB disconnected), it enters a retry/backoff state.

    If the failure persists beyond a set limit, it shuts down the application.
    """

    def __init__(
        self,
        audio_device_config: HardwareConfig,
        audio_queue: queue.Queue,
        stop_event: threading.Event,
    ):
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
        logger.debug(f"{self._class_name} initialized.")

        self._reconnect_delay_seconds = RECONNECT_DELAY_SECONDS
        self._max_retries = RECONNECT_MAX_RETRIES

    def run(self):
        """
        The main execution loop with built-in hardware recovery.

        Continuously reads audio chunks from the configured input device via
        `sounddevice.InputStream` and puts them onto the queue as tuples containing
        the audio data (numpy array) and a timestamp.

        1. Enters a 'Reconnection Loop'.
        2. Tries to open the InputStream.
        3. If successful, RESETS retry count and enters 'Read Loop'.
        4. If it fails, increments retry count.
        5. If retries exceed limit, signals app shutdown.
        """
        logger.info(f"{self._class_name} thread started.")

        retry_count = 0

        # --- 1. Reconnection Loop (The Watchdog) ---
        while not self._stop_event.is_set():
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
                    retry_count = 0

                    logger.debug(f"Microphone stream started on Device ID {device_id} at ({sample_rate}Hz).")

                    # --- 2. Read Loop (The Capture) ---
                    while not self._stop_event.is_set():
                        audio_chunk, overflow = stream.read(block_size)

                        if overflow:
                            logger.warning(
                                f"Input overflow detected on device {device_id}. Audio data lost from hardware buffer."
                            )

                        timestamp = DatetimeStamp.get()

                        # --- 3. Buffer Overflow Handling (Software side) ---
                        try:
                            if audio_chunk.ndim > 1:
                                audio_chunk = audio_chunk.flatten()

                            self._queue.put_nowait((audio_chunk, timestamp))

                        except queue.Full:
                            logger.warning(
                                "Consumer queue is full! Dropping audio chunk to maintain real-time monitoring."
                            )

            except (sd.PortAudioError, OSError) as e:
                retry_count += 1
                logger.error(f"Microphone Hardware Error (Attempt {retry_count}/{self._max_retries}): {e}")

                if retry_count >= self._max_retries:
                    logger.critical(
                        f"❌ Maximum reconnection attempts ({self._max_retries}) reached. "
                        "Assuming permanent hardware failure. Stopping application."
                    )
                    self._stop_event.set()
                    break

                logger.info(f"Waiting {self._reconnect_delay_seconds}s before reconnecting...")
                self._stop_event.wait(self._reconnect_delay_seconds)

            except Exception as e:
                logger.critical(f"Unexpected fatal error in ListenerThread: {e}", exc_info=True)
                self._stop_event.set()
                break

        logger.info(f"{self._class_name} thread finished.")
