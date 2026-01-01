"""
Defines configuration data structure for audio input devices.

This module hold settings such as sample rate, block size, data type,
and device ID used for opening audio streams.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

import logging

from .hardwares.selector import HardwareSelector
from .settings import get_settings

settings = get_settings()

logger = logging.getLogger(__name__)


class HardwareConfig:
    """
    Data class to store and manage configuration parameters for an audio input stream.

    This class consolidates all settings required by `sounddevice.InputStream`
    (or similar audio capture libraries) into a single, structured object.
    It calculates the `block_size` based on sample rate and buffer duration.
    """

    def __init__(
        self,
        target_audio_device: HardwareSelector,
        sample_rate: float,
        buffer_seconds: float,
        dtype: str | None = None,
        high_priority: bool | None = None,
    ):
        """
        Initializes the audio device configuration object.

        :param target_audio_device: An object representing the selected audio input device.
                                    Expected to have an 'id' attribute (e.g., an instance
                                    of HardwareSelector or a similar structure).
        :param sample_rate: The desired sample rate for the audio stream in Hertz (Hz)
                            (e.g., 48000.0, 16000.0).
        :param buffer_seconds: The desired duration of each audio buffer (chunk) in seconds.
                               This affects latency and processing granularity.
        :param dtype: The desired data type for the audio samples (e.g., 'float32', 'int16').
                      'float32' (range -1.0 to 1.0) is often preferred for processing.
                      Defaults to 'float32'.
        :param high_priority: A boolean flag indicating whether to request high-priority
                              processing for the audio stream from the operating system.
                              Crucial for real-time applications to prevent buffer overflows.
                              Defaults to False.
        """
        self.id = target_audio_device.id
        self.native_rate = target_audio_device.native_rate
        self.sample_rate = sample_rate
        self.buffer_seconds = buffer_seconds
        self.block_size = int(sample_rate * buffer_seconds)

        self.dtype = dtype if dtype is not None else settings.AUDIO.DTYPE
        self.high_priority = high_priority if high_priority is not None else settings.AUDIO.HIGH_PRIORITY

        logger.debug(
            f"HardwareConfig initialized: Device ID={self.id}, SR={self.sample_rate}Hz,"
            f"NR={self.native_rate}Hz Blocksize={self.block_size}, Dtype={self.dtype}"
        )
