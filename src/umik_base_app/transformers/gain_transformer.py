"""
Stateless transformer that applies sensitivity gain correction.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

import numpy as np

from .transformers_protocol import AudioTransformer


class GainTransformer(AudioTransformer):
    """
    Applies a scalar sensitivity gain to audio samples. O(n) operation.

    This transformer is stateless and can be used for cheap real-time
    level correction without the computational cost of FIR filtering.
    """

    def __init__(self, gain_linear: float):
        """
        Initialize the gain transformer.

        :param gain_linear: Linear gain factor (e.g., 1.0 = 0dB, 0.5 = -6dB).
        """
        self._gain = gain_linear

    @property
    def gain(self) -> float:
        """The linear gain factor."""
        return self._gain

    def process_audio(self, audio_chunk: np.ndarray) -> np.ndarray:
        """
        Apply gain to the audio chunk.

        :param audio_chunk: Input audio samples.
        :return: Gain-corrected audio samples.
        """
        return audio_chunk * self._gain
