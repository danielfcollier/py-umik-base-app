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

import contextlib
import logging
import os
import queue
import re
import threading
import time
from datetime import datetime

import sounddevice as sd

from .hardware_config import HardwareConfig
from .hardwares.selector import HardwareSelector
from .settings import get_settings
from .transports.base_transport import AudioTransport

logger = logging.getLogger(__name__)

settings = get_settings()


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
        transport: AudioTransport,
        stop_event: threading.Event,
    ):
        """
        Initializes the audio listener thread.

        :param audio_device_config: An object containing the configuration for the
                                    audio stream (e.g., sample rate, block size,
                                    device ID, dtype). This configuration dictates how
                                    the audio stream will be opened.
        :param transport: A thread-safe `AudioTransport` instance. Raw audio chunks
                          captured from the microphone will be put onto this transport.
        :param stop_event: A `threading.Event` object used to signal the thread
                           to terminate its loop and exit gracefully. This event
                           is typically set by the main application thread upon
                           receiving a shutdown signal (SIGINT/SIGTERM).
        """
        self._audio_device_config = audio_device_config
        self._transport = transport
        self._stop_event = stop_event

        self._class_name = self.__class__.__name__
        logger.debug(f"{self._class_name} initialized.")

        self._reconnect_delay_seconds = settings.RECONNECT_DELAY_SECONDS
        self._max_retries = settings.RECONNECT_MAX_RETRIES
        self._silence_check_interval = 1.0

    # Small callback blocksize so PortAudio fires frequently and disconnect is detected quickly.
    # The consumer sink handles accumulation to the desired interval independently.
    _CALLBACK_BLOCK_SIZE = 4096

    @staticmethod
    @contextlib.contextmanager
    def _suppress_alsa_stderr():
        """Redirect C-level fd 2 to /dev/null during PortAudio open/close operations.

        ALSA/PortAudio write error strings directly to the file descriptor, bypassing
        Python's logging. This context must NOT wrap the wait loop — Python's
        StreamHandler holds a reference to the original sys.stderr object (not the
        name), which writes to fd 2. Suppressing fd 2 for the stream lifetime would
        silently drop all Python log output too.
        """
        saved_fd = os.dup(2)
        devnull_fd = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull_fd, 2)
        os.close(devnull_fd)
        try:
            yield
        finally:
            os.dup2(saved_fd, 2)
            os.close(saved_fd)

    def _rediscover_device_id(self) -> int:
        # Strip the ALSA hardware address suffix "(hw:N,N)" so the search matches
        # the device regardless of which card index ALSA assigned after re-enumeration.
        base_name = re.sub(r"\s*\(hw:\d+,\d+\)\s*$", "", self._audio_device_config.name).strip()
        new_id = HardwareSelector.find_device_by_name(base_name)
        if new_id is not None and new_id != self._audio_device_config.id:
            logger.info(f"Device re-discovered at new ID {new_id} (was {self._audio_device_config.id})")
        return new_id if new_id is not None else self._audio_device_config.id

    def run(self):
        """
        The main execution loop with built-in hardware recovery.

        Uses a callback-based InputStream so the main loop never blocks inside
        stream.read(). PortAudio fires finished_callback when the device disappears
        (e.g. USB unplug), which sets a local Event and breaks the inner wait loop,
        causing the reconnection logic to kick in.

        1. Enters a 'Reconnection Loop'.
        2. Opens a callback InputStream.
        3. If successful, RESETS retry count and waits on stop/stream-end events.
        4. On stream end (disconnect), raises PortAudioError to trigger retry.
        5. If retries exceed limit, signals app shutdown.
        """
        logger.info(f"{self._class_name} thread started.")

        retry_count = 0

        # --- 1. Reconnection Loop (The Watchdog) ---
        while not self._stop_event.is_set():
            try:
                device_id = self._rediscover_device_id()
                sample_rate = self._audio_device_config.sample_rate
                dtype = self._audio_device_config.dtype

                last_audio = [time.monotonic()]

                def _callback(indata, frames, time_info, status):
                    last_audio[0] = time.monotonic()
                    if status.input_overflow:
                        logger.warning(f"Input overflow on device {device_id}. Audio data lost.")
                    try:
                        self._transport.send((indata.flatten().copy(), datetime.now()))
                    except queue.Full:
                        logger.warning("Consumer queue is full! Dropping audio chunk.")

                # Open and start with ALSA noise suppressed; suppress again on close.
                # The wait loop runs outside suppression so Python logging is unaffected.
                with self._suppress_alsa_stderr():
                    stream = sd.InputStream(
                        device=device_id,
                        blocksize=self._CALLBACK_BLOCK_SIZE,
                        samplerate=sample_rate,
                        dtype=dtype,
                        channels=1,
                        callback=_callback,
                    )
                    stream.start()

                retry_count = 0
                logger.debug(f"Microphone stream started on Device ID {device_id} at {sample_rate}Hz.")

                try:
                    # --- 2. Wait Loop — wakes on stop signal or silence timeout ---
                    while not self._stop_event.is_set():
                        self._stop_event.wait(timeout=self._silence_check_interval)
                        silence = time.monotonic() - last_audio[0]
                        if silence > self._reconnect_delay_seconds:
                            raise sd.PortAudioError(f"No audio for {silence:.1f}s — device likely disconnected")
                finally:
                    with self._suppress_alsa_stderr():
                        stream.close()

            except (sd.PortAudioError, OSError) as e:
                if self._stop_event.is_set():
                    break
                retry_count += 1
                max_label = "∞" if self._max_retries is None else self._max_retries
                logger.error(f"Microphone Hardware Error (Attempt {retry_count}/{max_label}): {e}")

                if self._max_retries is not None and retry_count >= self._max_retries:
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
