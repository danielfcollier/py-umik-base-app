"""
Defines the sink adapter for the audio recorder.

This module implements the `AudioSink` protocol, allowing the `RecorderSink`
to be used as a destination in the `AudioPipeline`. It handles data type conversion
(Float32 -> Int16) required for standard WAV format.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

import logging
from datetime import datetime

import numpy as np

from .recorder_sink import RecorderSink
from .sinks_protocol import AudioSink

logger = logging.getLogger(__name__)


class RecorderSinkAdapter(AudioSink):
    """
    Adapts the RecordingManager to the AudioSink protocol.
    """

    def __init__(self, manager: RecorderSink):
        """
        Initializes the adapter.

        :param manager: An instance of RecordingManager that handles the file I/O.
        """
        self._manager = manager

    def handle_audio(self, audio_chunk: np.ndarray, timestamp: datetime) -> None:
        """
        Receives a float32 audio chunk from the pipeline, converts it to int16,
        and passes it to the recording manager.
        """
        # Convert Float32 [-1.0, 1.0] to Int16 [-32768, 32767]
        # Clipping ensures we don't wrap around if the signal is too loud
        int16_chunk = (np.clip(audio_chunk, -1.0, 1.0) * 32767).astype(np.int16)

        # Convert numpy array to raw bytes
        audio_bytes = int16_chunk.tobytes()

        # Write to file
        self._manager.write(audio_bytes)
