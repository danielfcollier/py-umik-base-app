"""
Provides a robust manager for writing WAV files with automatic rotation.

This module handles the low-level details of opening, closing, and writing to
WAV files. It includes logic to automatically "rotate" (close and start new)
files based on a time duration to prevent data loss and file size limits.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

import logging
import wave
from pathlib import Path

from src.library.datetime_stamp import DatetimeStamp

logger = logging.getLogger(__name__)


ROTATION_DEFAULT_SECONDS = 3600  # 1 hour
DEFAULT_SAMPLE_RATE = 48000
DEFAULT_RECORDING_PATH = Path("recordings")


class AudioStreamsRecorder:
    """
    Manages WAV file recording with automatic file rotation.
    """

    def __init__(
        self,
        base_path: Path = Path(DEFAULT_RECORDING_PATH),
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        channels: int = 1,
        sample_width: int = 2,
        rotation_duration_seconds: int = ROTATION_DEFAULT_SECONDS,
    ):
        """
        Initializes the recording manager.

        :param base_path: The directory or base name for files. Files will be named
                          using this base + timestamp (e.g., "recordings/audio_2025-01-01_120000.wav").
        :param rotation_duration_seconds: How many seconds of audio to record before
                                          starting a new file.
        """
        self._base_path = base_path
        self._sample_rate = sample_rate
        self._channels = channels
        self._sample_width = sample_width
        self._rotation_frames = rotation_duration_seconds * sample_rate

        self._wave_file: wave.Wave_write | None = None
        self._current_file_frames = 0
        self._is_open = False

    def _generate_filename(self) -> str:
        """Generates a filename with the current timestamp."""
        timestamp = DatetimeStamp.get()

        if self._base_path.suffix:
            name = f"{self._base_path.stem}_{timestamp}{self._base_path.suffix}"
            return str(self._base_path.parent / name)

        return str(self._base_path / f"recording_{timestamp}.wav")

    def _rotate(self):
        """Closes the current file and opens a new one."""
        if self._is_open:
            self.close()

        self.open()

    def open(self):
        """Opens a new WAV file for writing."""
        if self._is_open:
            return

        filename = self._generate_filename()
        try:
            self._wave_file = wave.open(filename, "wb")
            self._wave_file.setnchannels(self._channels)
            self._wave_file.setsampwidth(self._sample_width)
            self._wave_file.setframerate(self._sample_rate)

            self._is_open = True
            self._current_file_frames = 0
            logger.info(f"Started new recording segment: {filename}")
        except Exception as e:
            logger.error(f"Failed to open WAV file {filename}: {e}")
            self._is_open = False
            raise

    def write(self, audio_bytes: bytes):
        """
        Writes audio bytes. Automatically rotates file if duration is exceeded.
        """
        if not self._is_open:
            return

        try:
            self._wave_file.writeframes(audio_bytes)

            # Calculate frames written in this chunk
            # bytes / (channels * width) = frames
            frames_in_chunk = len(audio_bytes) // (self._channels * self._sample_width)
            self._current_file_frames += frames_in_chunk

            # Check for rotation
            if self._current_file_frames >= self._rotation_frames:
                logger.info("Rotation limit reached. Switching files...")
                self._rotate()

        except Exception as e:
            logger.error(f"Error writing to file: {e}")

    def close(self):
        """Closes the current WAV file."""
        if self._is_open and self._wave_file:
            try:
                self._wave_file.close()
            except Exception as e:
                logger.error(f"Error closing WAV file: {e}")
            finally:
                self._is_open = False
                self._wave_file = None
