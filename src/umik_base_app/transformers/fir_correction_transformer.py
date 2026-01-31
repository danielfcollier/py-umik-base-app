"""
Stateful transformer that applies FIR frequency response correction.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

import numpy as np
from scipy.signal import lfilter

from .transformers_protocol import AudioTransformer


class FirCorrectionTransformer(AudioTransformer):
    """
    Applies FIR filter correction to audio samples. O(n * taps) operation.

    This transformer maintains internal filter state for streaming continuity.
    For discontinuous segments, call reset_state() before processing.
    """

    def __init__(self, filter_taps: np.ndarray):
        """
        Initialize the FIR correction transformer.

        :param filter_taps: FIR filter coefficients (taps).
        """
        self._filter_taps = filter_taps
        self._filter_state = np.zeros(len(filter_taps) - 1)

    @property
    def filter_taps(self) -> np.ndarray:
        """The FIR filter coefficients."""
        return self._filter_taps

    @property
    def num_taps(self) -> int:
        """Number of filter taps."""
        return len(self._filter_taps)

    def reset_state(self) -> None:
        """
        Reset the internal filter state to zeros.

        Call this when starting to process a new, discontinuous audio
        segment to avoid filter ringing artifacts from previous audio.
        """
        self._filter_state = np.zeros(len(self._filter_taps) - 1)

    def process_audio(self, audio_chunk: np.ndarray) -> np.ndarray:
        """
        Apply FIR filter to the audio chunk, maintaining state.

        :param audio_chunk: Input audio samples.
        :return: Frequency-corrected audio samples.
        """
        filtered_chunk, self._filter_state = lfilter(
            self._filter_taps, 1.0, audio_chunk, zi=self._filter_state
        )

        if filtered_chunk.dtype != audio_chunk.dtype:
            filtered_chunk = filtered_chunk.astype(audio_chunk.dtype)

        return filtered_chunk
