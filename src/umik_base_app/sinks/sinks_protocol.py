"""
Defines the protocols for audio processing components and data sinks.

This module establishes the contracts for AudioTransformer (transformers) and
AudioSink (consumers) to ensure modularity and type safety in the audio pipeline.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

from datetime import datetime
from typing import Protocol, runtime_checkable

import numpy as np


@runtime_checkable
class AudioSink(Protocol):
    """
    Protocol for components that consume audio data (e.g., Recorder, Meter, GUI).
    Input: Final Audio -> Output: None (Side Effect)
    """

    def handle_audio(self, audio_chunk: np.ndarray, timestamp: datetime) -> None: ...
