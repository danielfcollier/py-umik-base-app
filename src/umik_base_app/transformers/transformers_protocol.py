"""
Defines the protocols for audio processing components and data sinks.

This module establishes the contracts for AudioTransformer (transformers) and
AudioSink (consumers) to ensure modularity and type safety in the audio pipeline.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

from typing import Protocol, runtime_checkable

import numpy as np


@runtime_checkable
class AudioTransformer(Protocol):
    """
    Protocol for components that transform audio data (e.g., CalibratorTransformer, Filter).
    Input: Raw Audio -> Output: Processed Audio
    """

    def process_audio(self, audio_chunk: np.ndarray) -> np.ndarray: ...
